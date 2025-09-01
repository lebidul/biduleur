from bs4 import BeautifulSoup

def extract_events(input_file):
    with open(input_file, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")
    events = soup.find_all("p", style="font-family: Arial Narrow;line-height:0.25")
    return events

def split_events_into_blocks(events, num_blocks=6):
    total_lines = len(events)
    lines_per_bloc = total_lines // num_blocks
    extra_lines = total_lines % num_blocks

    blocs = []
    start = 0
    for i in range(num_blocks):
        end = start + lines_per_bloc + (1 if i < extra_lines else 0)
        blocs.append(events[start:end])
        start = end
    return blocs
