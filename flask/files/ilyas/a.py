import xlrd
import pandas as pd
import datetime as d

# Open the workbook and select the first worksheet
wb = xlrd.open_workbook('task1.xlsx')
sh = wb.sheet_by_index(0)
# List to hold dictionaries
task_list = []
# Iterate through each row in worksheet and fetch values into dict
for rownum in range(1, sh.nrows):
    task_list.append(sh.row_values(rownum))

# array to df
columns = [col.lower() for col in sh.row_values(0)]
df = pd.DataFrame(task_list, columns=columns)

# formatting date column
df.date = [d.datetime(*xlrd.xldate_as_tuple(date, wb.datemode)) for date in df.date]

# split year and month
df['month'] = [date.day for date in df.date]
df['year'] = [date.year for date in df.date]

# dropping old date column inplace
df.drop('date', axis=1, inplace=True)

# split df by pizza categories
categories = df.category.unique()
df = [df[df.category == cat] for cat in categories]