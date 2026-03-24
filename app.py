from dash import Dash, html

app = Dash()
server = app.server

app.layout = [html.Div(children='Hello, Dash!')]

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=True)