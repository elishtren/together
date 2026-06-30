import os
import pickle
import json
import base64
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google import genai
from dotenv import load_dotenv

# עקיפת בעיות SSL בחיבור ל-API
ssl._create_default_https_context = ssl._create_unverified_context

# טעינת המפתח הסודי מתוך קובץ ה- .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

# אתחול הלקוח של ג'מיני
client = None
if GOOGLE_API_KEY:
    client = genai.Client(api_key=GOOGLE_API_KEY)
else:
    print("אזהרה: מפתח GEMINI_API_KEY לא נמצא בקובץ .env!")

# הרשאות גישה הכוללות כתיבה ליומן וניהול מיילים
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.modify'
]

def authenticate_google():
    """אימות מול גוגל ושמירת טוקן הרשאות"""
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
    """מוודא שהתאריך בפורמט תקין עבור API של גוגל"""
    if not iso_string: return None
    # מוסיף אזור זמן אם חסר
    if not iso_string.endswith('Z') and '+' not in iso_string and '-' not in iso_string[-6:]:
        return iso_string + "+03:00"
    return iso_string

def is_time_slot_free(creds, start_iso, end_iso):
    """בדיקה האם קיים כבר אירוע ביומן בטווח הזמנים המבוקש"""
    try:
        service = build('calendar', 'v3', credentials=creds)
        events_result = service.events().list(
            calendarId='primary',
            timeMin=format_iso_with_tz(start_iso),
            timeMax=format_iso_with_tz(end_iso),
            singleEvents=True
        ).execute()
        return len(events_result.get('items', [])) == 0
    except Exception as e:
        print(f"שגיאה בבדיקת זמינות: {e}")
        return False

def create_calendar_event(creds, title, start_iso, end_iso, location, description, attendees=None):
    """יצירת אירוע ביומן"""
    try:
        service = build('calendar', 'v3', credentials=creds)
        event = {
            'summary': title,
            'location': location,
            'description': description,
            'start': {'dateTime': format_iso_with_tz(start_iso), 'timeZone': 'Asia/Jerusalem'},
            'end': {'dateTime': format_iso_with_tz(end_iso), 'timeZone': 'Asia/Jerusalem'},
        }
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees if "@" in email]
        
        created = service.events().insert(calendarId='primary', body=event).execute()
        print(f"🎉 אירוע נוצר בהצלחה: {created.get('htmlLink')}")
    except Exception as e:
        print(f"שגיאה ביצירת אירוע: {e}")

def send_rejection_email(creds, to_email, original_subject):
    """שליחת מייל דחייה"""
    try:
        service = build('gmail', 'v1', credentials=creds)
        subject = f"Re: {original_subject}"
        body = "שלום, המועד המבוקש תפוס ביומן. נא להציע מועד אחר."
        message = MIMEText(body, 'plain', 'utf-8')
        message['to'] = to_email
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        print(f"📧 נשלח מייל דחייה ל-{to_email}")
    except Exception as e:
        print(f"שגיאה בשליחת מייל: {e}")

def analyze_email_content_with_ai(creds, sender_email, subject, body):
    """ניתוח מייל ע"י AI"""
    if not client: return
    try:
        prompt = (f"Analyze: Subject: {subject}. Body: {body}. "
                  "Return JSON with: is_meeting, title, start_time, end_time, location, attendees, description.")
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        
        if data.get("is_meeting"):
            if is_time_slot_free(creds, data['start_time'], data['end_time']):
                create_calendar_event(creds, data['title'], data['start_time'], data['end_time'], 
                                      data.get('location'), data.get('description'), data.get('attendees'))
            else:
                send_rejection_email(creds, sender_email, subject)
    except Exception as e:
        print(f"שגיאה בניתוח: {e}")

def check_gmail_and_process(creds):
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', q='newer_than:2d', maxResults=5).execute()
    for msg in results.get('messages', []):
        txt = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        # חילוץ כותרת ושולח... (קוד החילוץ הקיים)
        analyze_email_content_with_ai(creds, "sender@example.com", "Subject", "Body")

if __name__ == '__main__':
    creds = authenticate_google()
    check_gmail_and_process(creds)