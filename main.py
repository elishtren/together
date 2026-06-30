import os
import pickle
import json
import base64
import ssl
import time
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google import genai
from dotenv import load_dotenv

# עקיפת בעיות SSL
ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

# יצירת הקליינט עם מפתח ה-API
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

def authenticate_google():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/gmail.modify'])
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
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
        service.events().insert(calendarId='primary', body=event).execute()
        print(f"✅ הצלחה: האירוע '{title}' נוצר ביומן!")
    except Exception as e:
        print(f"❌ שגיאה ביצירת אירוע ביומן: {e}")

def analyze_email_content_with_ai(creds, subject, body):
    if not client: return
    print(f"🔍 מנתח מייל: {subject}")
    
    try:
        # שימוש במודל גנרי שנתמך ב-API הנוכחי
        prompt = "Extract meeting details. Return ONLY valid JSON:\n"
        prompt += '{"is_meeting": true, "title": "...", "start_time": "YYYY-MM-DDTHH:MM:SS", "end_time": "YYYY-MM-DDTHH:MM:SS", "location": "...", "description": "..."}\n'
        prompt += f"Subject: {subject}\nBody: {body}"
        
        # שימוש במודל gemini-2.0-flash
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        
        # ניקוי המחרוזת מסימני מרקדאון לפני פענוח JSON
        clean_text = response.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        
        if data.get("is_meeting"):
            print(f"💡 זיהיתי פגישה: {data.get('title')}")
            create_calendar_event(creds, data['title'], data['start_time'], data.get('end_time', data['start_time']), data.get('location', ''), data.get('description', ''))
        else:
            print("ℹ️ לא זוהתה פגישה במייל זה.")
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בניתוח ה-AI: {e}")
        return True

def check_gmail_and_process(creds):
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=1).execute()
    messages = results.get('messages', [])
    
    if not messages:
        print("לא נמצאו הודעות חדשות.")
        return

    for msg in messages:
        txt = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        subject = next((h['value'] for h in txt['payload']['headers'] if h['name'].lower() == 'subject'), 'ללא נושא')
        body = ""
        if 'parts' in txt['payload']:
            for part in txt['payload']['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
        
        analyze_email_content_with_ai(creds, subject, body)
        time.sleep(5)

if __name__ == '__main__':
    creds = authenticate_google()
    check_gmail_and_process(creds)