from typing import List, Optional, Literal, Union
from pydantic import BaseModel, EmailStr, Field, field_validator, root_validator, model_validator
from datetime import datetime

from app.settings import ALL_ROLES

class UserIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    username: str = Field(min_length=3, max_length=30)
    roles: List[Literal["user", "admin", "staff"]] = ["user"]
    
    @field_validator("roles", mode="before")
    @classmethod
    def validate_roles(cls, v):
        if isinstance(v, list):
            for role in v:
                if role not in ALL_ROLES:
                    raise ValueError(f"Role '{role}' is not allowed. Choose from {ALL_ROLES}.")
        elif v not in ALL_ROLES:
            raise ValueError(f"Role '{v}' is not allowed. Choose from {ALL_ROLES}.")
        return v

class UserOut(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    full_name: str
    username: str
    roles: List[str]
    bio: Optional[str] = ""
    profile_image: Optional[str] = ""
    token: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class MeReturn(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    full_name: str
    username: str
    roles: List[str]
    bio: Optional[str] = ""
    profile_image: Optional[str] = ""

class TokenData(BaseModel):
    email: Optional[str] = None
    roles: List[Literal["user", "admin", "staff"]] = ["user"]

class UpdateProfile(BaseModel):
    full_name: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None

class ExamCategoryCreate(BaseModel):
    name: str = Field(..., example="วิทยาศาสตร์")
    description: Optional[str] = Field(None, example="หมวดวิชาวิทยาศาสตร์")
    english_name: Optional[str] = Field(None, json_schema_extra={"example": "Science"})

class ExamCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    english_name: Optional[str] = None

class ExamCategoryOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    english_name: Optional[str] = None

class ExamFileCreate(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "Midterm Physics"})
    description: str = Field(..., json_schema_extra={"example": "Grade 11 physics midterm"})
    tags: List[str] = Field(default_factory=list)
    essay_count: int = Field(0, ge=0, description="จำนวนข้อเขียน")
    choice_count: int = Field(0, ge=0, description="จำนวนข้อกา")

    @model_validator(mode="after")
    def at_least_one_question_type(self):
        essay = getattr(self, 'essay_count', 0)
        choice = getattr(self, 'choice_count', 0)
        if (essay < 1 and choice < 1):
            raise ValueError('ต้องมีอย่างน้อย 1 ใน 2 (essay_count หรือ choice_count) ที่เป็น 1 ขึ้นไป')
        return self

class ExamFileUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    essay_count: Optional[int] = Field(None, ge=0, description="จำนวนข้อเขียน")
    choice_count: Optional[int] = Field(None, ge=0, description="จำนวนข้อกา")

    @model_validator(mode="after")
    def at_least_one_question_type_update(self):
        essay = self.essay_count
        choice = self.choice_count
        if essay is not None or choice is not None:
            if (essay or 0) < 1 and (choice or 0) < 1:
                raise ValueError('ต้องมีอย่างน้อย 1 ใน 2 (essay_count หรือ choice_count) ที่เป็น 1 ขึ้นไป')
        return self

class ExamFileOut(BaseModel):
    id: str
    title: str
    description: str
    tags: List[str]
    url: str
    uploaded_by: str
    essay_count: int
    choice_count: int

class AdminUserOut(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    full_name: str
    username: str
    roles: List[str]
    bio: Optional[str] = ""
    profile_image: Optional[str] = ""
    created_at: Optional[datetime] = None

class UpdateUserRole(BaseModel):
    role: Literal["user", "admin", "staff", "seller"]
    
    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ALL_ROLES:
            raise ValueError(f"Role '{v}' is not allowed. Choose from {ALL_ROLES}.")
        return v

class BookmarkCreate(BaseModel):
    exam_id: str

class BookmarkOut(BaseModel):
    id: str
    user_id: str
    exam_id: str
    created_at: datetime

class ExamQuestion(BaseModel):
    id: str
    type: Literal["multiple_choice", "fill", "essay"]
    question: str
    choices: Optional[List[str]] = None  # for multiple_choice
    answer: Optional[Union[str, List[str]]] = None  # สำหรับเฉลย (admin)

class ExamAnswerCreate(BaseModel):
    question_id: str
    answer: Union[str, List[str]]

class ExamSubmissionCreate(BaseModel):
    exam_id: str
    answers: List[ExamAnswerCreate]

class ExamAnswerOut(BaseModel):
    question_id: str
    answer: Union[str, List[str]]
    is_correct: Optional[bool] = None

class ExamSubmissionOut(BaseModel):
    id: str
    user_id: str
    exam_id: str
    answers: List[ExamAnswerOut]
    submitted_at: datetime

# ------------------- MARKET MODELS -------------------

# Answer checking
class AnswerCheckRequest(BaseModel):
    question_id: str
    answer: str

class AnswerCheckResult(BaseModel):
    correct: bool
class MarketItemOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None

class MarketItemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
