import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
# שימוש ב-SDK החדש והרשמי של גוגל
from google import genai
from dotenv import load_dotenv

# טעינת המפתח הסודי מתוך קובץ ה- .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

# אתחול הלקוח של ג'מיני בגרסה החדשה והרשמית
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

def analyze_email_with_ai(subject):
    """פונקציה המשתמשת ב-SDK החדש לניתוח הכותרת"""
    if not client:
        return "שגיאה: ה-AI לא אותחל בגלל מפתח לא תקין או חסר."
    try:
        # קריאה למודל העדכני של 2026 עם המבנה החדש
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"נתח את כותרת המייל הבאה: '{subject}'. האם מדובר בבקשה לפגישה או משימה שיש לה תאריך? ענה במשפט אחד קצר.",
        )
        return response.text.strip()
    except Exception as e:
        return f"שגיאה בניתוח ה-AI: {e}"

def check_gmail(creds):
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])
    
    print(f"\n--- [Gmail + AI] ניתוח המיילים בתיבה עם ה-SDK החדש: ---")
    for msg in messages:
        txt = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = txt['payload']['headers']
        subject = "ללא כותרת"
        for header in headers:
            if header['name'].lower() == 'subject':
                subject = header['value']
                break
        
        # הפעלת ה-AI על כותרת המייל
        ai_analysis = analyze_email_with_ai(subject)
        print(f"המייל: {subject}")
        print(f"ניתוח ה-AI: {ai_analysis}\n")

if __name__ == '__main__':
    credentials = authenticate_google()
    check_gmail(credentials)