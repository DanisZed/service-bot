from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/master", tags=["master-panel"])


class VerifyCodeRequest(BaseModel):
    code: str


@router.post("/auth/request-code")
async def request_code():
    # TODO: тут ты шлёшь код мастеру в MAX через твоего второго бота
    # Сейчас просто вернём OK, чтобы фронт работал
    return {"ok": True}


@router.post("/auth/verify-code")
async def verify_code(payload: VerifyCodeRequest):
    # TODO: тут ты проверяешь код и выдаёшь реальный JWT/токен
    # Пока отдаём фиктивный токен
    if not payload.code:
        raise HTTPException(status_code=400, detail="Empty code")

    return {
        "access_token": "TEST_TOKEN",
        "master_id": 1,
        "name": "Тестовый мастер",
    }

class ServiceRequest(BaseModel):
    id: int
    master_seq: int | None = None
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    service_title: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    
    class Config:
        from_attributes = True


@router.get("/requests", response_model=List[ServiceRequest])
async def list_requests():
    # TODO: тут будет реальное чтение из БД
    # Пока вернём пару тестовых заявок
    return [
        ServiceRequest(
            id=1,
            client_name="Иван",
            client_phone="+7 900 000-00-00",
            service_title="Ремонт стиралки",
            address="Улица Пушкина, дом Колотушкина",
            status="new",
        ),
        ServiceRequest(
            id=2,
            client_name="Мария",
            client_phone="+7 901 111-11-11",
            service_title="Диагностика холодильника",
            address="Проспект Ленина, 10",
            status="in_progress",
        ),
    ]