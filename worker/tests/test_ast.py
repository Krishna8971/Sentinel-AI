from core.ast_parser import parse_fastapi_code

def test_ast_parser_extracts_routes():
    code = """
from fastapi import FastAPI, Depends

app = FastAPI()

def get_current_user():
    return "user"

@app.get('/users/me')
def read_current_user(current_user: str = Depends(get_current_user)):
    return {"user": current_user}

@app.post('/items')
async def create_item(item: dict = Depends(get_current_user)):
    return item
"""
    endpoints = parse_fastapi_code(code)
    assert len(endpoints) == 2
    assert endpoints[0]['path'] == '/users/me'
    assert endpoints[0]['method'] == 'GET'
    assert 'get_current_user' in endpoints[0]['guards']
    assert endpoints[1]['method'] == 'POST'
    assert 'get_current_user' in endpoints[1]['guards']
