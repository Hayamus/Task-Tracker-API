from pydantic import Field, BaseModel

class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=24)
    description: str = Field(max_length=1200)

class Team(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str
    members_count: int