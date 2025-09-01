from jinja2 import Environment, FileSystemLoader

def render_template(template_dir, template_name, context, output_file):
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)
    html_output = template.render(**context)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_output)
