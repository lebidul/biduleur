def get_pages_to_process(doc, filename):
    # ignore_last = False
    # try:
    #     year = int(filename[:4])
    #     month = int(filename[5:7])
    #     if year > 2013 or (year == 2013 and month >= 11):
    #         ignore_last = True
    # except:
    #     pass
    ignore_last = True
    max_pages = len(doc)
    if ignore_last and max_pages >= 3:
        max_pages = 2
    return max_pages, ignore_last
