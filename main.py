import os
import pickle
import json
import base64
from datetime import datetime
from email.mime.text import MIMEText
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google import genai
from dotenv import load_dotenv

# טעינת המפתח הסודי מתוך קובץ ה- .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

# אתחול הלקוח של ג'מיני
client = None
if GOOGLE_API_KEY:
    client = genai.Client(api_key=GOOGLE_API_KEY)
else:
    print("אזהרה: מפתח GEMINI_API_KEY לא נמצא בקובץ .env!")

# הרשאות גישה הכוללות כתיבה ליומן וניהול מיילים (שליחה/שינוי)
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.modify'
]

def authenticate_google():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    print("החיבור לגוגל בוצע בהצלחה מלאה!")
    return creds

def format_iso_with_tz(iso_string):
    """מוודא שלזמן ה-ISO יש סיומת אזור זמן תקינה עבור גוגל (Asia/Jerusalem הוא +03:00 בקיץ)"""
    if not iso_string:
        return iso_string
    if not iso_string.endswith('Z') and '+' not in iso_string and '-' not in iso_string[-6:]:
        return iso_string + "+03:00"
    return iso_string

def is_time_slot_free(creds, start_iso, end_iso):
    """בדיקה האם קיים כבר אירוע ביומן בטווח הזמנים המבוקש"""
    try:
        service = build('calendar', 'v3', credentials=creds)
        
        # הבטחת פורמט זמנים תקין עם אזור זמן
        start_formatted = format_iso_with_tz(start_iso)
        end_formatted = format_iso_with_tz(end_iso)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_formatted,
            timeMax=end_formatted,
            singleEvents=True
        ).execute()
        events = events_result.get('items', [])
        return len(events) == 0
    except Exception as e:
        print(f"שגיאה בבדיקת זמינות היומן: {e}")
        return False

def create_calendar_event(creds, title, start_iso, end_iso, location, description, attendees=None):
    """יצירת אירוע ביומן גוגל כולל מיקום, תיאור ורשימת משתתפים מוזמנים"""
    try:
        service = build('calendar', 'v3', credentials=creds)
        
        event = {
            'summary': title,
            'location': location,
            'description': description,
            'start': {
                'dateTime': format_iso_with_tz(start_iso),
                'timeZone': 'Asia/Jerusalem',
            },
            'end': {
                'dateTime': format_iso_with_tz(end_iso),
                'timeZone': 'Asia/Jerusalem',
            },
        }
        
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees if "@" in email]
        
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"🎉 אירוע דינמי נוצר ביומן בהצלחה: {created_event.get('htmlLink')}")
    except Exception as e:
        print(f"שגיאה ביצירת אירוע ביומן: {e}")

def send_rejection_email(creds, to_email, original_subject):
    """שליחת מייל סירוב אוטומטי אם השעה תפוסה ביומן"""
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        subject = f"Re: {original_subject}"
        body = (
            "שלום רב,\n\n"
            "תודה על פנייתך לקביעת פגישה.\n"
            "מערכת ה-AI בדקה את לוח השנה שלי ומצאה כי המועד המוצע כבר תפוס.\n"
            "לצערי לא ניתן לקיים את הפגישה בזמן זה. אנא הצע מועד אחר.\n\n"
            "בברכה,\n"
            "סוכן ה-AI האוטומטי שלך"
        )
        
        message = MIMEText(body, 'plain', 'utf-8')
        message['to'] = to_email
        message['subject'] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        print(f"📧 נשלח מייל סירוב אוטומטי לשולח: {to_email}")
    except Exception as e:
        print(f"שגיאה בשליחת מייל הסירוב: {e}")

def analyze_email_content_with_ai(creds, sender_email, subject, body):
    """ה-AI מנתח את המלל החופשי ומחלץ תאריך, שעה, מיקום ומשתתפים"""
    if not client:
        return
    try:
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        prompt = (
            f"Current time: {current_time_str}. "
            f"Analyze this email. Subject: {subject}. Body: {body}. "
            "Task: Check if this email is asking for a meeting/class/interview. "
            "If NO, return exactly: {\"is_meeting\": false} "
            "If YES, extract details and return a valid JSON only (no backticks, no markdown) with these keys: "
            "\"is_meeting\" (true), "
            "\"title\" (in Hebrew), "
            "\"start_time\" (ISO 8601 string), "
            "\"end_time\" (ISO 8601 string, 1 hour later if not specified), "
            "\"location\" (in Hebrew, or 'לא נקבע מיקום'), "
            "\"attendees\" (list of email addresses mentioned in the mail body, or empty list if none), "
            "\"description\" (brief summary in Hebrew)."
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        clean_json_text = response.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json_text)
        
        if data.get("is_meeting"):
            print(f"🤖 ה-AI זיהה פגישה במלל החופשי!")
            print(f"   📋 כותרת: {data.get('title')}")
            print(f"   📅 זמן: {data.get('start_time')} עד {data.get('end_time')}")
            print(f"   📍 מיקום: {data.get('location')}")
            print(f"   👥 מוזמנים נוספים מהמייל: {data.get('attendees')}")
            
            start_iso = data.get("start_time")
            end_iso = data.get("end_time")
            
            if is_time_slot_free(creds, start_iso, end_iso):
                print("📅 המועד פנוי! יוצר אירוע ביומן...")
                create_calendar_event(
                    creds,
                    title=data.get("title"),
                    start_iso=start_iso,
                    end_iso=end_iso,
                    location=data.get("location"),
                    description=data.get("description"),
                    attendees=data.get("attendees")
                )
            else:
                print("❌ אזהרה: המועד המבוקש תפוס ביומן! מתחיל תהליך דחייה...")
                send_rejection_email(creds, sender_email, subject)
        else:
            print(f"המייל '{subject}' נותח: לא נמצאה פגישה במלל החופשי.")
            
    except Exception as e:
        print(f"שגיאה בניתוח ה-AI או בפענוח ה-JSON: {e}")

def check_gmail_and_process(creds):
    service = build('gmail', 'v1', credentials=creds)
    
    results = service.users().messages().list(userId='me', q='newer_than:2d', maxResults=5).execute()
    messages = results.get('messages', [])
    
    print(f"\n--- [Gmail AI Content Parser] סריקת הודעות מהיומיים האחרונים: ---")
    if not messages:
        print("לא נמצאו מיילים חדשים מהיומיים האחרונים.")
        return

    for msg in messages:
        txt = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        headers = txt['payload']['headers']
        
        subject = "ללא כותרת"
        sender_email = "שולח לא ידוע"
        for header in headers:
            if header['name'].lower() == 'subject':
                subject = header['value']
            elif header['name'].lower() == 'from':
                sender_email = header['value']
                if "<" in sender_email and ">" in sender_email:
                    sender_email = sender_email.split("<")[1].split(">")[0]
        
        body = ""
        if 'parts' in txt['payload']:
            parts = txt['payload']['parts']
            for part in parts:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                    break
        elif 'body' in txt['payload'] and 'data' in txt['payload']['body']:
            body = base64.urlsafe_b64decode(txt['payload']['body']['data']).decode('utf-8', errors='ignore')
            
        analyze_email_content_with_ai(creds, sender_email, subject, body)
        print("-" * 50)

if __name__ == '__main__':
    credentials = authenticate_google()
    check_gmail_and_process(credentials)