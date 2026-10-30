from pydantic import BaseModel


class UserDTO(BaseModel):
    id: str
    name: str

    model_config = {
        'from_attributes': True
    }
