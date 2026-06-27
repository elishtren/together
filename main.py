import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# הרשאות מעודכנות - קריאה בלבד למייל וגישה מלאה ליומן
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
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            
    print("החיבור לגוגל בוצע בהצלחה מלאה!")
    return creds

def check_gmail(creds):
    service = build('gmail', 'v1', credentials=creds)
    # מושך את 5 המיילים האחרונים בתיבה
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])
    
    print(f"\n--- [Gmail] מצאתי {len(messages)} מיילים בתיבה: ---")
    for msg in messages:
        txt = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = txt['payload']['headers']
        subject = "ללא כותרת"
        for header in headers:
            if header['name'].lower() == 'subject':
                subject = header['value']
                break
        print(f"- {subject}")

def check_calendar(creds):
    service = build('calendar', 'v3', credentials=creds)
    # מושך את 5 האירועים הקרובים ביותר ביומן
    results = service.events().list(calendarId='primary', maxResults=5, singleEvents=True, orderBy='startTime').execute()
    events = results.get('items', [])
    
    print(f"\n--- [Google Calendar] האירועים הקרובים ביומן: ---")
    if not events:
        print("היומן ריק מאירועים כרגע.")
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(f"- {event['summary']} ({start})")

if __name__ == '__main__':
    # הרצת התהליך המלא
    credentials = authenticate_google()
    check_gmail(credentials)
    check_calendar(credentials)