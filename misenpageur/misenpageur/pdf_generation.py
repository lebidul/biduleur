from weasyprint import HTML, CSS

def generate_pdf(html_file, output_pdf, css=None):
    HTML(html_file).write_pdf(output_pdf, stylesheets=[css] if css else [])
