from jinja2 import Template

HTML_TEMPLATE_WITH_IMAGE_OLD = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Instagram Image</title>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    height: 100vh;
                    width: 100vw;
                    background-image: url('../frames/202501_298.jpg');
                    background-size: contain;
                    background-position: center;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    
                }
                .text {
                    color: #FF0000;
                    font-size: 2rem;
                    font-family: Cutive Mono, sans-serif;
                    text-shadow: 2px 2px 5px rgba(0, 0, 0, 0.7);
                    text-align: left;
                }
            </style>
        </head>
        <body>
            <div class="text">
                <p>{{ content }}</p>
            </div>
        </body>
        </html>
    """

HTML_TEMPLATE_GREEN_GREY_ORANGE_OLD = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Instagram Image</title>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    height: 100vh;
                    width: 100vw;
                    background-color: #313438;
                    background-position: center;
                    display: flex;
                    justify-content: center;
                    align-items: center;

                }
                .text {
                    color: #5F826B;
                    font-size: 20px;
                    font-family: Cutive Mono, sans-serif;
                    text-shadow: 2px 2px 5px rgba(0, 0, 0, 0.7);
                    text-align: left;
                }
            </style>
        </head>
        <body>
            <div class="top-left">Le Bidul</div>
            <div class="top-right">Samedi 5 Janvier</div>
            <div class="text">
                {{ content }}
            </div>
        </body>
        </html>
    """


HTML_TEMPLATE_GREEN_GREY_ORANGE = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Instagram Image</title>
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    height: 100vh;
                    width: 100vw;
                    background-color: #313438;
                    background-position: center;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    position: relative;
                    flex-direction: column;
                }
                .text-header {
                    font-size: 3rem;
                    margin-top: 100px; /* Adjust spacing below the top-left element */
                    color: #5F826B;
                    text-align: left;
                    font-family: Lucida Console;
                }
                .text {
                    color: #5F826B;
                    font-size: 3rem;
                    font-family: Lucida Console;
                    text-shadow: 2px 2px 5px rgba(0, 0, 0, 0.7);
                    text-align: left;
                }
                .top-left,
                .top-right {
                    position: absolute;
                    top: 20px;
                    font-family: Lucida Console;
                    font-size: 4rem;
                    color: #5F826B;
                    text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7);
                }
                .top-left {
                    left: 25px;
                }
                .top-right {
                    right: 25px;
                    text-align: right;
                }
            </style>
        </head>
        <body>
            <div class="top-left">Le Bidul<br><span style="color:#CF8E6D">{{ date }}</span></div>
            <div class="text-header">Événements du jour passés sous le radar du Bidul:</div>
            <div class="text">
                {{ content }}
            </div>
        </body>
        </html>
    """




# Function to render a template with variables
def render_template(template_str, **kwargs):
    template = Template(template_str)
    return template.render(**kwargs)
