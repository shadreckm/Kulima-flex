from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional
from ..schemas.dtos import DocumentResponse
from ..services.document_adapter import save_uploaded_file, InvalidUploadError
from ..services.run_repository import RunRepository
from ..core.auth import get_current_user, AuthenticatedUser
from ..core.rate_limit import check_rate_limit
from kulima.db import IntelligenceRepository

router = APIRouter()
_run_repo = RunRepository()
_brief_repo = IntelligenceRepository()


@router.post("/", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    runId: Optional[str] = Form(None),
    user: AuthenticatedUser = Depends(get_current_user),
):
    check_rate_limit(user.user_id, "documents:upload")

    if runId:
        run_str = str(runId).strip()
        existing_user_id: Optional[str] = None
        run_found = False

        # 1. Check live in-memory/api_runs
        live_info = _run_repo.get_run(run_str)
        if live_info is not None:
            run_found = True
            existing_user_id = live_info.get("user_id")
        
        # 2. Check stored SQLite intelligence_runs
        if not run_found and run_str.isdigit():
            db_run = _brief_repo.get_run(int(run_str))
            if db_run is not None:
                run_found = True
                existing_user_id = db_run.get("user_id")

        # 3. If run exists and has private owner, enforce 403 Forbidden
        if run_found and existing_user_id is not None and existing_user_id != user.user_id:
            raise HTTPException(status_code=403, detail={"error": True, "message": "Access denied: run belongs to another user"})

    try:
        res = save_uploaded_file(file, run_uuid=runId, user_id=user.user_id)
    except InvalidUploadError:
        raise HTTPException(status_code=400, detail="Unsupported file type or payload too large")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return res

