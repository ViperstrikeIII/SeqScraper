import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import re
import base64
import textwrap
import os

# Import pipelines from other scripts
from id_mapper import run_mapping_pipeline 
from blast_tools import build_blast_db, run_tblastn, extract_hit_sequences

# Initialize the Dash app with a Bootstrap theme
app = dash.Dash(__name__, title="SeqScraper", external_stylesheets=[dbc.themes.FLATLY])

# Define the Dash Layout
app.layout = dbc.Container([
    # Header Row
    dbc.Row([
            html.H1("SeqScraper: UniProt Gene Mapper", className="text-center my-4 fw-bold text-primary")
    ]),
    
    # Input Section
    dbc.Row([
        # Column/Card 1: Gene Input
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Label("Enter Gene Names (separated by commas, spaces, or newlines):", className="fw-bold mb-2"),
                    dbc.Textarea(
                        id='gene-input',
                        placeholder='e.g., brca1, cox1, atp6',
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
                    
                    # Upload box
                    dcc.Upload(
                        id='upload-fasta',
                        children=html.Div([
                            'Drag and Drop or ',
                            html.A('Select a FASTA File', className="fw-bold text-primary")
                        ]),
                        style={
                            'width': '100%',
                            'height': '100x',
                            'lineHeight': '100px',
                            'borderWidth': '2px',
                            'borderStyle': 'dashed',
                            'borderRadius': '5px',
                            'textAlign': 'center',
                            'cursor': 'pointer',
                            'backgroundColor': '#f8f9fa'
                        },
                        multiple=False # Keeps replacing file kept in data folder with new upload
                    ),
                    # Small text area to show the user if the upload worked
                    html.Div(id='upload-status', className="mt-3 text-center small"),
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
                            filter_action="native",
                            filter_options={"case": "insensitive"},
                            style_table={'overflowX': 'auto'},
                            style_cell={
                                'textAlign': 'left', 
                                'padding': '12px',
                                'fontFamily': 'inherit',
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
            ),
            html.Hr(className="my-5"), # A visual separator line
            
            # BLAST Search section
            html.H4("Run BLAST Search", className="mb-3"),
            dbc.Button(
                "Execute BLAST", 
                id="run-blast-button", 
                color="danger",
                className="fw-bold w-100 mb-3"
            ),
            
            # Spinner for the BLAST wait time
            dbc.Spinner(
                color="danger",
                children=[
                    html.Div(id="blast-status-message", className="mb-3 text-center fw-bold"),

                    # BLAST results table
                    dash_table.DataTable(
                        columns=[
                                        {"name": "Query ID", "id": "Query ID"},
                                        {"name": "Subject ID", "id": "Subject ID"},
                                        {"name": "% Identity", "id": "% Identity"},
                                        {"name": "Alignment Length", "id": "Alignment Length"},
                                        {"name": "Mismatches", "id": "Mismatches"},
                                        {"name": "Gap Opens", "id": "Gap Opens"},
                                        {"name": "Q. Start", "id": "Q. Start"},
                                        {"name": "Q. End", "id": "Q. End"},
                                        {"name": "S. Start", "id": "S. Start"},
                                        {"name": "S. End", "id": "S. End"},
                                        {"name": "E-value", "id": "E-value"},
                                        {"name": "Bit Score", "id": "Bit Score"}
                                    ],
                        id='blast-results-table',
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'left', 'padding': '10px'},
                        style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'},
                        page_size=10,
                        row_selectable="multi",
                        selected_rows=[],
                        filter_action="native",
                        sort_action="native",
                    ),
                    # Download button
                    dbc.Button(
                        "Extract & Download Selected Hits", 
                        id="download-hits-btn", 
                        color="success", 
                        className="fw-bold w-100 mt-3"
                    )
                ]
            )
        ], width=12)
    ]),
    dcc.Download(id="download-final-fasta")
], fluid=True, className="p-5")

# -------------------
# Callback Functions
# -------------------

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

        # Save to the data volume
        save_path = "/app/data/target_sequences.fasta"
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
    """
    On click of save fasta button, saves selected protein sequences to a fasta file stored in data folder.

    Args:
        n_clicks: makes sure button is clicked before activating
        selected_rows: list of indexes to retrieve from table_data
        table_data: dataframe of uniprot protein sequences
    """
    if not selected_rows:
        return "Please select at least one sequence from the table.", "mt-2 text-center fw-bold text-warning"
    if not table_data:
        return "", ""

    fasta_lines = []
    
    for row_index in selected_rows:
        row = table_data[row_index]
        accession = row.get("Entry", "Unknown_ID")
        gene_name = row.get("From", "Unknown_Gene")
        organism = row.get("Organism", "Unknown_Organism")
        sequence = row.get("Sequence", "")
        
        if not sequence:
            continue 
            
        # Format FASTA: >Accession_GeneName Organism
        header = f">{accession}_{gene_name} {organism}"
        wrapped_sequence = "\n".join(textwrap.wrap(sequence, width=80)) # Wrap sequences for readibility (if a user wanted to look)
        fasta_lines.append(f"{header}\n{wrapped_sequence}")

    final_fasta_string = "\n".join(fasta_lines)
    output_path = "/app/data/query_sequences.fasta"
    
    try:
        with open(output_path, "w") as f:
            f.write(final_fasta_string)
        return f"Saved {len(selected_rows)} sequence(s) to query_sequences.fasta! Ready for BLAST.", "mt-2 text-center fw-bold text-success"
    except Exception as e:
        return f"Error saving file: {str(e)}", "mt-2 text-center fw-bold text-danger"
    
# Callback 4: Run BLAST
@app.callback(
    Output('blast-results-table', 'data'),
    Output('blast-status-message', 'children'),
    Output('blast-status-message', 'className'),
    Input('run-blast-button', 'n_clicks'),
    State('upload-fasta', 'filename'), # Check if file has been uploaded
    prevent_initial_call=True
)
def execute_blast_pipeline(n_clicks, uploaded_filename):
    """
    Run blast pipeline from blast_tools.py and return dataframe to dashboard
    """
    # Determine file paths based on our Docker volume structure
    query_fasta = "/app/data/query_sequences.fasta"
    
    # Safety checks
    if not uploaded_filename:
        return [], "Please upload a Target FASTA file first.", "text-warning"
        
    db_fasta = "/app/data/target_sequences.fasta"

    # Check if fasta sequences
    if not os.path.exists(query_fasta):
        return [], "Please save selected UniProt sequences to FASTA first.", "text-warning"
    
    if not os.path.exists(db_fasta):
        return [], "Target FASTA file not found on server. Try uploading again.", "text-warning"

    try:
        # 1. Build the database
        build_blast_db(db_fasta)
        
        # 2. Run the search
        results_df = run_tblastn(query_fasta, db_fasta)
        
        if results_df.empty:
            return [], "BLAST completed successfully, but found 0 matching hits.", "text-primary"
            
        return results_df.to_dict('records'), f"BLAST completed! Found {len(results_df)} hits.", "text-success"
        
    except Exception as e:
        return [], f"BLAST Pipeline Error: {str(e)}", "text-danger"
    
@app.callback(
    Output('download-final-fasta', 'data'),
    Input('download-hits-btn', 'n_clicks'),
    State('blast-results-table', 'selected_rows'),
    State('blast-results-table', 'data'),
    State('upload-fasta', 'filename'),
    prevent_initial_call=True
)
def download_final_sequences(n_clicks, selected_rows, table_data, uploaded_filename):
    """
    On click of download button, use selected hits to extract sequences from target 
    fasta database and save as fasta file. Send download file to user
    """
    # Checks if any dependencies are not found
    if not selected_rows or not table_data or not uploaded_filename:
        return dash.no_update
        
    db_fasta = "/app/data/target_sequences.fasta"
    
    # Grab the full data dictionaries for only the checked rows
    selected_hits = [table_data[i] for i in selected_rows]
    
    # Run blastdbcmd to generate the final file
    final_file_path = extract_hit_sequences(db_fasta, selected_hits)
    
    # Send the file to the user's browser
    return dcc.send_file(final_file_path)
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)