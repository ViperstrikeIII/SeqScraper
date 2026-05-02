import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import re
import base64
import textwrap

# Import the pipeline we built in the other file
from id_mapper import run_mapping_pipeline 

# Initialize the Dash app with a Bootstrap theme
app = dash.Dash(__name__, title="SeqScraper", external_stylesheets=[dbc.themes.FLATLY])

# Define the Layout (The UI)
app.layout = dbc.Container([
    # Header Row
    dbc.Row([
            html.H1("SeqScraper: UniProt Gene Mapper", className="text-center my-4 fw-bold text-primary")
    ]),
    
    # Input Section wrapped in a nice Card
    dbc.Row([
        # Column 1: Gene Input
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Label("Enter Gene Names (separated by commas, spaces, or newlines):", className="fw-bold mb-2"),
                    dbc.Textarea(
                        id='gene-input',
                        placeholder='e.g., ndhF, cox1, atp6',
                        rows=4,
                        className="mb-3" 
                    ),
                    dbc.Button(
                        'Search UniProt', 
                        id='search-button', 
                        n_clicks=0, 
                        color="primary", 
                        className="w-100 fw-bold" 
                    )
                ])
            ], className="shadow-sm mb-4 h-100")
        ], md=6),

        # Column 2: FASTA Upload
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Label("Upload Target FASTA (Nucleotide):", className="fw-bold mb-2"),

                    dcc.Upload(
                        id='upload-fasta',
                        children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select a FASTA File', className="fw-bold text-primary")
                        ]),
                        style={
                            'width': '100%',
                            'height': '108px',
                            'lineHeight': '108px',
                            'borderWidth': '2px',
                            'borderStyle': 'dashed',
                            'borderRadius': '5px',
                            'textAlign': 'center',
                            'cursor': 'pointer',
                            'backgroundColor': '#f8f9fa'
                        },
                        multiple=False # We only want one target database at a time
                    ),
                    # Small text area to show the user if the upload worked
                    html.Div(id='upload-status', className="mt-3 text-center small")
                ])
            ], className="shadow-sm mb-4 h-100") 
        ], md=6)
    ]),

    # Results Section
    dbc.Row([
        dbc.Col([
            dbc.Spinner(
                color="primary",
                children=[
                    html.Div(id='table-container', children=[
                        # Table header
                        html.H4("UniProt Results", className="mb-3"),

                        # Instructions
                        html.P(
                            "Please choose one representative sequence for each entry in the Gene Name column.", 
                            className="text-muted small mb-3 fst-italic"
                        ),

                        # Actual table
                        dash_table.DataTable(
                            id='uniprot-results-table',
                            columns=[
                                {"name": "Gene Name", "id": "From"},
                                {"name": "Entry", "id": "Entry"},
                                {"name": "Entry Name", "id": "Entry Name"},
                                {"name": "Protein names", "id": "Protein names"},
                                {"name": "Gene Names", "id": "Gene Names"},
                                {"name": "Organism", "id": "Organism"},
                                {"name": "Length", "id": "Length"}
                            ],
                            data=[], 
                            row_selectable="multi", 
                            selected_rows=[],
                            page_size=15,
                            style_table={'overflowX': 'auto'},
                            style_cell={
                                'textAlign': 'left', 
                                'padding': '12px',
                                'fontFamily': 'inherit', # Inherit the Bootstrap font
                                'whiteSpace': 'normal',
                                'height': 'auto',
                            },
                            style_header={
                                'backgroundColor': '#f8f9fa',
                                'fontWeight': 'bold',
                                'borderBottom': '2px solid #dee2e6'
                            }
                        )
                    ]),
                    dbc.Button(
                        "Save Selected as FASTA", 
                        id="save-fasta-button", 
                        color="success", 
                        className="mt-3 fw-bold"
                    ),
                    html.Div(id="save-status-message", className="mt-2 text-success fw-bold")
                ]
            )
        ], width=12)
    ])
], fluid=True, className="p-5")

@app.callback(
    Output('uniprot-results-table', 'data'),
    Input('search-button', 'n_clicks'),
    State('gene-input', 'value'),
    prevent_initial_call=True 
)
def update_table(n_clicks, gene_string):
    """
    On click of search button, send list of gene names to uniprot requests API.

    Args:
        n_clicks: checks if button has been clicked to activate function
        gene_string: text entered into box; list of gene names
    """
    if not gene_string:
        return [] 
    
    gene_list = [g.strip() for g in re.split(r'[,\n\s]', gene_string) if g.strip()]
    
    df = run_mapping_pipeline(gene_list)
    
    if df is not None and not df.empty:
        return df.to_dict('records')
    
    return []

@app.callback(
    Output('upload-status', 'children'),
    Input('upload-fasta', 'contents'),
    State('upload-fasta', 'filename'),
    prevent_initial_call=True 
)
def handle_fasta_upload(contents, filename):
    """
    Reads in a file from user input and uploads file to persistant data volume

    Args:
        contents: file uploaded through dash
        filename: name of file from dash
    """
    # Check if contents is None or empty
    if not contents:
        return ""

    # Make sure contents is a single str, not a list
    if isinstance(contents, list):
        contents = contents[0]
        filename = filename[0]

    # Ensure the base64 comma separator actually exists
    if ',' not in contents:
        return html.Span("Upload error: File data is missing the base64 header.", className="text-danger fw-bold")

    try:
        content_type, content_string = contents.split(',', 1)
        
        # Decode the raw bytes
        decoded_file = base64.b64decode(content_string)

        # Save to the Docker mapped volume
        save_path = f"/app/data/{filename}"
        with open(save_path, "wb") as f:
            f.write(decoded_file)
            
        return html.Span(f"Successfully uploaded: {filename}", className="text-success fw-bold")
        
    except Exception as e:
        return html.Span(f"Error saving file: {str(e)}", className="text-danger fw-bold")
    
@app.callback(
    Output('save-status-message', 'children'),
    Output('save-status-message', 'className'),
    Input('save-fasta-button', 'n_clicks'),
    State('uniprot-results-table', 'selected_rows'), 
    State('uniprot-results-table', 'data'),          
    prevent_initial_call=True
)
def save_selected_to_fasta(n_clicks, selected_rows, table_data):
    if not selected_rows:
        return "Please select at least one sequence from the table.", "mt-2 text-center fw-bold text-warning"
    if not table_data:
        return "", ""

    fasta_lines = []
    
    for row_index in selected_rows:
        row = table_data[row_index]
        accession = row.get("Entry", "Unknown_ID")
        gene_name = row.get("Gene Name", "Unknown_Gene")
        organism = row.get("Organism", "Unknown_Organism")
        sequence = row.get("Sequence", "")
        
        if not sequence:
            continue 
            
        # Format FASTA: >Accession_GeneName Organism
        header = f">{accession}_{gene_name} {organism}"
        wrapped_sequence = "\n".join(textwrap.wrap(sequence, width=80))
        fasta_lines.append(f"{header}\n{wrapped_sequence}")

    final_fasta_string = "\n\n".join(fasta_lines)
    output_path = "/app/data/query_sequences.fasta"
    
    try:
        with open(output_path, "w") as f:
            f.write(final_fasta_string)
        return f"Saved {len(selected_rows)} sequence(s) to query_sequences.fasta! Ready for BLAST.", "mt-2 text-center fw-bold text-success"
    except Exception as e:
        return f"Error saving file: {str(e)}", "mt-2 text-center fw-bold text-danger"
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)