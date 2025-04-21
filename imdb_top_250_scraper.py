import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

url = 'https://www.imdb.com/chart/top/'
resp = requests.get(url)
soup = BeautifulSoup(resp.text, 'html.parser')
movies = soup.select('td.titleColumn')
ratings = soup.select('td.ratingColumn strong')

data = []
for i, m in enumerate(movies):
    title = m.a.text
    year = m.span.text.strip('()')
    rating = ratings[i].text
    detail_url = 'https://www.imdb.com' + m.a['href']
    det = BeautifulSoup(requests.get(detail_url).text, 'html.parser')
    genres = [g.text for g in det.find_all('span', class_='ipc-chip__text')]
    data.append({
        'Title': title,
        'Year': int(year),
        'Rating': float(rating),
        'Genres': ', '.join(genres)
    })
    time.sleep(0.3)

df = pd.DataFrame(data)

with pd.ExcelWriter('imdb_top_250.xlsx', engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name='Top 250', index=False, startrow=1, header=False)
    book  = writer.book
    sheet = writer.sheets['Top 250']
    header_fmt = book.add_format({
        'bold': True,
        'font_color': 'white',
        'bg_color': '#333399',
        'align': 'center'
    })
    for col_num, col_name in enumerate(df.columns):
        sheet.write(0, col_num, col_name, header_fmt)
    end_row = len(df) + 1
    sheet.add_table(f'A1:D{end_row}', {
        'columns': [
            {'header': 'Title'},
            {'header': 'Year'},
            {'header': 'Rating'},
            {'header': 'Genres'},
        ],
        'style': 'Table Style Medium 9'
    })
    wrap_fmt = book.add_format({'text_wrap': True, 'valign': 'top'})
    sheet.set_column('A:A', 40, wrap_fmt)
    sheet.set_column('B:B', 8,  wrap_fmt)
    sheet.set_column('C:C', 8,  wrap_fmt)
    sheet.set_column('D:D', 30, wrap_fmt)
    sheet.freeze_panes(1, 0)
