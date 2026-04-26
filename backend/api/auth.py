"""
Auth routes — signup, login, GitHub connect
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import orm
from backend.models.schemas import UserCreate, UserLogin, UserResponse, TokenResponse, GitHubConnectRequest
from backend.auth.jwt import hash_password, verify_password, create_access_token, get_current_user
from github import Github, GithubException

router = APIRouter()


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(orm.User).filter(orm.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(orm.User).filter(orm.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username taken")

    user = orm.User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(orm.User).filter(orm.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: orm.User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.post("/github/connect")
def connect_github(
    payload: GitHubConnectRequest,
    current_user: orm.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate and store a GitHub personal access token."""
    try:
        gh = Github(payload.github_token)
        gh_user = gh.get_user()
        github_username = gh_user.login
    except GithubException:
        raise HTTPException(status_code=400, detail="Invalid GitHub token")

    current_user.github_token = payload.github_token
    current_user.github_username = github_username
    db.commit()

    return {"status": "connected", "github_username": github_username}


@router.delete("/github/disconnect")
def disconnect_github(
    current_user: orm.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.github_token = None
    current_user.github_username = None
    db.commit()
    return {"status": "disconnected"}
