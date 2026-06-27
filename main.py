import os
import pickle
import json
from datetime import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google import genai
from dotenv import load_dotenv

# טעינת המפתח הסודי
load_dotenv()
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

client = None
if GOOGLE_API_KEY:
    client = genai.Client(api_key=GOOGLE_API_KEY)
else:
    print("אזהרה: מפתח GEMINI_API_KEY לא נמצא בקובץ .env!")

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.readonly'
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

def create_calendar_event(creds, title, start_iso, end_iso, location, description):
    try:
        service = build('calendar', 'v3', credentials=creds)
        event = {
            'summary': title,
            'location': location,
            'description': description,
            'start': {'dateTime': start_iso, 'timeZone': 'Asia/Jerusalem'},
            'end': {'dateTime': end_iso, 'timeZone': 'Asia/Jerusalem'},
        }
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"🎉 אירוע דינמי נוצר ביומן בהצלחה: {created_event.get('htmlLink')}")
    except Exception as e:
        print(f"שגיאה ביצירת אירוע ביומן: {e}")

def analyze_email_content_with_ai(creds, subject, body):
    if not client:
        return
    try:
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # פרומפט נקי לחלוטין משורות מפוצלות - מונע SyntaxError ב-100%
        prompt = (
            f"Current time: {current_time_str}. "
            f"Analyze this email. Subject: {subject}. Body: {body}. "
            "Task: Check if this email is asking for a meeting/class/interview. "
            "If NO, return exactly: {\"is_meeting\": false} "
            "If YES, extract details and return a valid JSON only (no backticks, no markdown) with these keys: "
            "\"is_meeting\" (true), \"title\" (in Hebrew), \"start_time\" (ISO 8601 string), \"end_time\" (ISO 8601 string, 1 hour later if not specified), \"location\" (in Hebrew, or 'לא נקבע מיקום'), \"description\" (brief summary in Hebrew)."
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
            print(f"   📅 זמן: {data.get('start_time')}")
            print(f"   📍 מיקום: {data.get('location')}")
            
            create_calendar_event(
                creds,
                title=data.get("title"),
                start_iso=data.get("start_time"),
                end_iso=data.get("end_time"),
                location=data.get("location"),
                description=data.get("description")
            )
        else:
            print(f"המייל '{subject}' נותח: לא נמצאה פגישה במלל החופשי.")
            
    except Exception as e:
        print(f"שגיאה בניתוח ה-AI או בפענוח ה-JSON: {e}")

def check_gmail_and_process(creds):
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])
    
    print(f"\n--- [Gmail AI Content Parser] ניתוח מלל חופשי מלא: ---")
    for msg in messages:
        txt = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        headers = txt['payload']['headers']
        
        subject = "ללא כותרת"
        for header in headers:
            if header['name'].lower() == 'subject':
                subject = header['value']
                break
        
        body = ""
        if 'parts' in txt['payload']:
            parts = txt['payload']['parts']
            for part in parts:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    import base64
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                    break
        elif 'body' in txt['payload'] and 'data' in txt['payload']['body']:
            import base64
            body = base64.urlsafe_b64decode(txt['payload']['body']['data']).decode('utf-8', errors='ignore')
            
        analyze_email_content_with_ai(creds, subject, body)
        print("-" * 50)

if __name__ == '__main__':
    credentials = authenticate_google()
    check_gmail_and_process(credentials)