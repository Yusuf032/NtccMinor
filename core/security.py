from fastapi.security import OAuth2PasswordBearer
import os
from dotenv import load_dotenv
load_dotenv()

AUTH_URL=os.getenv("AUTH_URL")
oauth2_scheme_doctor=OAuth2PasswordBearer(tokenUrl=f"{AUTH_URL}/doctor/login",scheme_name="doctor")
oauth2_scheme_patient=OAuth2PasswordBearer(tokenUrl=f"{AUTH_URL}/patient/login",scheme_name="patient")
