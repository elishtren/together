import os
import pickle
from datetime import datetime, timedelta
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

def create_calendar_event(creds, title):
    """פונקציה חדשה שיוצרת אירוע ביומן גוגל למחר בשעה 10:00 בבוקר"""
    try:
        service = build('calendar', 'v3', credentials=creds)
        
        # תזמון אוטומטי למחר ב-10:00 בבוקר
        tomorrow = datetime.now() + timedelta(days=1)
        start_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1) # פגישה של שעה
        
        event = {
            'summary': title,
            'description': 'נוצר אוטומטית על ידי מערכת ה-AI מה-Gmail שלך',
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Asia/Jerusalem',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Asia/Jerusalem',
            },
        }
        
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"🎉 אירוע נוצר ביומן בהצלחה: {created_event.get('htmlLink')}")
    except Exception as e:
        print(f"שגיאה ביצירת אירוע ביומן: {e}")

def analyze_email_and_schedule(creds, subject):
    """פונקציה שמנתחת את המייל ומחליטה אם לזמן פגישה ביומן"""
    if not client:
        return
    try:
        # ביקשנו מה-AI לענות בפורמט מובנה כדי שהקוד יוכל לקבל החלטה
        prompt = (
            f"נתח את כותרת המייל הבאה: '{subject}'. "
            f"האם מדובר בבקשה לפגישה, דיון או משהו שצריך לתזמן ביומן? "
            f"ענה אך ורק במילה אחת: 'YES' או 'NO'."
        )
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        decision = response.text.strip().upper()
        print(f"המייל: {subject} -> החלטת ה-AI לתזמון: {decision}")
        
        # אם ה-AI קבע שזה דורש פגישה - נתזמן אוטומטית ביומן!
        if "YES" in decision:
            print(f"🤖 ה-AI זיהה צורך בפגישה! מייצר אירוע עבור: '{subject}'...")
            create_calendar_event(creds, subject)
            
    except Exception as e:
        print(f"שגיאה בניתוח ה-AI: {e}")

def check_gmail_and_process(creds):
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])
    
    print(f"\n--- [Gmail + AI + Calendar] תהליך אוטומטי משולב: ---")
    for msg in messages:
        txt = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = txt['payload']['headers']
        subject = "ללא כותרת"
        for header in headers:
            if header['name'].lower() == 'subject':
                subject = header['value']
                break
        
        # מפעילים את הניתוח שגם יוצר אירוע ביומן במידת הצורך
        analyze_email_and_schedule(creds, subject)
        print("-" * 40)

if __name__ == '__main__':
    credentials = authenticate_google()
    check_gmail_and_process(credentials)