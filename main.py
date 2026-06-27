import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
# הגדרת הרשאות הגישה (Scopes) בהתאם למה שהגדרנו בגוגל קלאוד
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar'
]

def main():
    creds = None
    # בדיקה אם קיים כבר טוקן ישן
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # אם אין טוקן תקין, נבצע תהליך התחברות
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # שמירת הטוקן לפעמים הבאות
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    print("ההתחברות לגוגל הצליחה לחלוטין! קובץ token.json נוצר.")

if __name__ == '__main__':
    main()
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# הגדרת ההרשאות שאנחנו מבקשים מהמשתמש (גישה ליומן ולמיילים)
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.modify'
]

def authenticate_google():
    creds = None
    # קובץ token.pickle שומר את התחברות המשתמש כדי שלא נצטרך לאשר בדפדפן כל פעם מחדש
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # אם אין אישור בתוקף, נבקש מהמשתמש להתחבר
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # שמירת האישור לפעמים הבאות
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            
    print("החיבור לגוגל בוצע בהצלחה מלאה!")
    return creds

if __name__ == '__main__':
    authenticate_google()