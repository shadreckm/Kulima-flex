from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional
from ..schemas.dtos import DocumentResponse
from ..services.document_adapter import save_uploaded_file, InvalidUploadError
from ..services.run_repository import RunRepository
from ..core.auth import get_current_user, AuthenticatedUser
from ..core.rate_limit import check_rate_limit

router = APIRouter()
_run_repo = RunRepository()


@router.post("/", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    runId: Optional[str] = Form(None),
    user: AuthenticatedUser = Depends(get_current_user),
):
    # Rate limit hook (no-op in pre-beta)
    check_rate_limit(user.user_id, "documents:upload")

    # If runId is provided, ensure it belongs to the authenticated user.
    if runId:
        info = _run_repo.get_run(runId)
        if not info or info.get("user_id") != user.user_id:
            raise HTTPException(status_code=401, detail={"error": True, "message": "Unauthorized"})
    try:
        res = save_uploaded_file(file, run_uuid=runId, user_id=user.user_id)
    except InvalidUploadError:
        # Unsupported type or size
        raise HTTPException(status_code=400, detail="Unsupported file type")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return res
