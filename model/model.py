from pydantic import BaseModel, Field
from typing import List, Optional


class BasicDetails(BaseModel):
    date: str = Field(..., description="Date of the consultation in YYYY-MM-DD format")
    patient_name: str = Field(..., description="Full name of the patient")
    doctor_name: str = Field(..., description="Full name of the doctor")

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-03-15",
                "patient_name": "John Doe",
                "doctor_name": "Dr. Smith"
            }
        }


class ClinicalDetails(BaseModel):
    clinic_name: str = Field(..., description="Name of the clinic or hospital")
    phone_number: str = Field(..., description="Contact phone number of the clinic or hospital")
    address: str = Field(..., description="Address of the clinic or hospital")

    class Config:
        json_schema_extra = {
            "example": {
                "clinic_name": "City Health Clinic",
                "phone_number": "+1-555-0123",
                "address": "123 Medical Plaza, Downtown"
            }
        }


class PatientDetails(BaseModel):
    age: int = Field(..., description="Age of the patient")
    gender: str = Field(..., description="Gender of the patient")
    CIN_1: str = Field(..., description="CIN (unique ID) of the patient")

    class Config:
        json_schema_extra = {
            "example": {
                "age": 35,
                "gender": "Male",
                "CIN_1": "PATIENT123456"
            }
        }


class Diagnosis(BaseModel):
    symptoms: str = Field(..., description="Symptoms reported by the patient")
    description: str = Field(..., description="Detailed description of the diagnosis")

    class Config:
        json_schema_extra = {
            "example": {
                "symptoms": "Fever, Cough, Headache",
                "description": "Patient presents with viral flu symptoms lasting 3 days."
            }
        }


class DoctorDetails(BaseModel):
    CIN_2: Optional[str] = Field(None, description="CIN (unique ID) of the doctor")

    class Config:
        json_schema_extra = {
            "example": {
                "CIN_2": "DOC987654"
            }
        }


class PrescribedItem(BaseModel):
    name: str = Field(..., description="Name of the prescribed item")
    dosage: str = Field(..., description="Dosage of the prescribed item")
    frequency: str = Field(..., description="Frequency of the prescribed item")
    duration: str = Field(..., description="Duration for which the item is prescribed")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Paracetamol",
                "dosage": "500mg",
                "frequency": "Twice daily",
                "duration": "5 days"
            }
        }


class Prescription(BaseModel):
    CIN_1: str = Field(..., description="CIN (unique ID) of the patient")
    CIN_2: str = Field(default=None, description="CIN (unique ID) of the doctor")
    basic_details: BasicDetails = Field(..., description="Basic details of the consultation")
    clinical_details: ClinicalDetails = Field(..., description="Clinical details of the clinic or hospital")
    patient_details: PatientDetails = Field(..., description="Details of the patient")
    diagnosis: Diagnosis = Field(..., description="Diagnosis details including symptoms and description")
    prescribed_items: List[PrescribedItem] = Field(..., description="List of prescribed items")

    class Config:
        json_schema_extra = {
            "example": {
                "CIN_1": "PATIENT123456",
                "CIN_2": "DOC987654",
                "basic_details": {
                    "date": "2024-03-15",
                    "patient_name": "John Doe",
                    "doctor_name": "Dr. Smith"
                },
                "clinical_details": {
                    "clinic_name": "City Health Clinic",
                    "phone_number": "+1-555-0123",
                    "address": "123 Medical Plaza, Downtown"
                },
                "patient_details": {
                    "age": 35,
                    "gender": "Male",
                    "CIN_1": "PATIENT123456"
                },
                "diagnosis": {
                    "symptoms": "Fever, Cough",
                    "description": "Viral Flu"
                },
                "prescribed_items": [
                    {
                        "name": "Paracetamol",
                        "dosage": "500mg",
                        "frequency": "Twice daily",
                        "duration": "5 days"
                    }
                ]
            }
        }


class OldPrescription(BaseModel):
    CIN_1: str = Field(..., description="CIN (unique ID) of the patient")
    basic_details: BasicDetails = Field(..., description="Basic details of the consultation")
    patient_details: PatientDetails = Field(..., description="Details of the patient")
    diagnosis: Diagnosis = Field(..., description="Diagnosis details including symptoms and description")
    clinical_details: ClinicalDetails = Field(..., description="Clinical details of the clinic or hospital")
    prescribed_items: List[PrescribedItem] = Field(..., description="List of prescribed items")

    class Config:
        json_schema_extra = {
            "example": {
                "CIN_1": "PATIENT123456",
                "basic_details": {
                    "date": "2024-03-10",
                    "patient_name": "Jane Doe",
                    "doctor_name": "Dr. Adams"
                },
                "patient_details": {
                    "age": 28,
                    "gender": "Female",
                    "CIN_1": "PATIENT123456"
                },
                "diagnosis": {
                    "symptoms": "Headache",
                    "description": "Migraine"
                },
                "clinical_details": {
                    "clinic_name": "Community Hospital",
                    "phone_number": "+1-555-9876",
                    "address": "456 Health St"
                },
                "prescribed_items": [
                    {
                        "name": "Ibuprofen",
                        "dosage": "400mg",
                        "frequency": "As needed",
                        "duration": "3 days"
                    }
                ]
            }
        }



class LoadEmbeddingsRequest(BaseModel):
    CIN_1: str = Field(..., description="Unique Clinical Identifier (CIN) of the patient")

    class Config:
        json_schema_extra = {
            "example": {
                "CIN_1": "PATIENT123456"
            }
        }


class SearchEmbeddingsRequest(BaseModel):
    CIN_1: str = Field(..., description="Unique Clinical Identifier (CIN) of the patient")
    query: str = Field(..., description="Natural language query to search for similar records")
    limit: Optional[int] = Field(10, description="Maximum number of records to return (default: 10)")

    class Config:
        json_schema_extra = {
            "example": {
                "CIN_1": "PATIENT123456",
                "query": "fever and headache",
                "limit": 5
            }
        }


class QueryRequest(BaseModel):
    CIN_1: str = Field(..., description="Unique Clinical Identifier (CIN) of the patient")
    query: str = Field(..., description="Question to ask about the patient's medical history")
    limit: Optional[int] = Field(10, description="Maximum number of context records to use (default: 10)")

    class Config:
        json_schema_extra = {
            "example": {
                "CIN_1": "PATIENT123456",
                "query": "What medications is the patient taking for hypertension?",
                "limit": 10
            }
        }


