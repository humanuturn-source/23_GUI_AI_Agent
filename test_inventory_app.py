from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()
ITEMS = []


@app.get("/inventory", response_class=HTMLResponse)
def inventory_page():
    rows = "".join(f"<li>{i['name']} — Qty: {i['qty']}</li>" for i in ITEMS)
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Local Inventory Dashboard</title></head>
    <body>
      <h1>Serengeti Field Inventory</h1>
      <form method="post" action="/inventory">
        <label for="item_name">Item Name</label>
        <input id="item_name" name="item_name" type="text" required />
        <label for="quantity">Quantity</label>
        <input id="quantity" name="quantity" type="text" required />
        <button id="submit_btn" type="submit">Add Item</button>
      </form>
      <div id="banner">{"Item added successfully!" if ITEMS else "Ready"}</div>
      <ul>{rows}</ul>
    </body>
    </html>
    """


@app.post("/inventory", response_class=HTMLResponse)
def add_item(item_name: str = Form(...), quantity: str = Form(...)):
    ITEMS.append({"name": item_name, "qty": quantity})
    return inventory_page()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)
