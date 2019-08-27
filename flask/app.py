from flask import Flask, render_template, session, request, redirect, url_for, g, flash
from werkzeug.utils import secure_filename
import sqlite3
import json
import os


import pandas as pd
import datetime as d
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

UPLOAD_FOLDER = 'files'
ALLOWED_EXTENSIONS = {'xls', 'xlsx'}
user = {}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login')
def login():
    if request.args:
        return render_template('login.html', error = request.args['err'])
    else:
        return render_template('login.html')

@app.route('/login/submit', methods=['POST'])
def login_submit():
    conn = sqlite3.connect('pizzazza.db')
    c = conn.cursor()
    c.execute("select * from users where uname='" + request.form['uname'] + "'")
    record = c.fetchone()
    conn.commit()
    conn.close()

    session.pop('user', None)
    if record:
        if record[1] == request.form['pass']:
            session['user'] = request.form['uname']
            user['full_name'] = record[2]
            return redirect(url_for('home'))
    
    return redirect(url_for('login', err='Login failed! Try again...'))

@app.before_request
def before_request():
    g.user = None
    if 'user' in session:
        g.user = session['user']

@app.route('/home')
def home():
    if g.user:
        conn = sqlite3.connect('pizzazza.db')
        c = conn.cursor()
        c.execute("select * from tasks where user='" + g.user + "'")
        records = c.fetchall()
        conn.commit()
        conn.close()
        new_records = "["
        for record in records:
            new_records += '{"name": "' + record[0] + '", "file_name": "' + record[1] + '", "step": "' + str(record[2]) + '", "user": "' + record[3] + '", "start": "NULL", "end": "NULL", "status": "Not started", "operation": "Start"},'
        records = new_records[:len(new_records)-1] + ']'
        print(records)
        return render_template('home.html', user=user['full_name'], tasks=records)
    
    return redirect(url_for('login'))

@app.route('/new-task')
def new_task():
    if g.user:
        if len(request.args) == 2:
            return render_template('new_task.html', error = request.args['err'], user=user['full_name'])
        else:
            return render_template('new_task.html', user=user['full_name'])
    
    return redirect(url_for('login'))

@app.route('/add-task')
def add_task():
    if g.user:
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return 'No file part'
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return 'No selected file'
        if file and allowed_file(file.filename):

            # adding task to database
            conn = sqlite3.connect('pizzazza.db')
            c = conn.cursor()
            try:
                c.execute("insert into tasks(name, file, step, user) values('" + request.form['task-name'] + "', '" + request.form['task-name'] + ".xlsx', " + request.form['step'] + ", '" + g.user + "')")
                conn.commit()
                conn.close()

                # adding file to server directory
                save_dir = os.path.join(app.config['UPLOAD_FOLDER'], g.user)
                if not os.path.exists(save_dir):
                    os.mkdir(save_dir)
                file.save(os.path.join(save_dir, request.form['task-name'] + '.xlsx'))

                return 'Task created...'

            except sqlite3.IntegrityError:
                return 'The task name already exists! Choose another task name...'

@app.route('/analysis/<string:file_name>/<int:step>')
def analysis(file_name, step):
    if g.user:
        read_dir = os.path.join(app.config['UPLOAD_FOLDER'], g.user)
        df = pd.read_excel(read_dir + '/' + file_name)
        df.columns = [col.lower() for col in df.columns]
        df.category = [cat.replace(' ', '_').replace('\xa0', '_') for cat in df.category]

        # split year and month
        df.date = [d.datetime(date.year, date.day, date.day) for date in df.date]
        df['month'] = [date.month for date in df.date]
        df['year'] = [date.year for date in df.date]

        # sorting df
        df = df.sort_values(['category', 'year', 'month']).reset_index(drop=True)

        # getting unique pizza categories
        cats = df.category.unique()

        # filling nan values
        for cat in cats:
            df[df.category == cat] = df[df.category == cat].fillna(df[df.category == cat].mean())
            
        regr = RandomForestRegressor(random_state=1, n_estimators=25, n_jobs=-1)

        def next_date(year, month):
            if month < 12:
                return year, month+1
            else:
                return year+1, 1
            
        dfs_new = pd.DataFrame(columns=['year', 'month', 'predicted', 'category'])
        predicted = []
        for cat in cats:
            X, y = df[df.category == cat][['year', 'month']], df[df.category == cat].sales
            #X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, random_state=42)
            #regr.fit(X_train, y_train)
            regr.fit(X, y)
            predicted += list(regr.predict(X))
            
            #plt.plot(range(len(dfs[cat])), y)
            #plt.plot(range(len(dfs[cat])), predicted)
            #plt.show()
            
            year = X.tail(1).year.iloc[0]
            month = X.tail(1).month.iloc[0]
            X_new = []
            for i in range(step):
                year, month = next_date(year, month)
                X_new.append([d.datetime(year, month, 1), year, month])
            
            X_new = pd.DataFrame(X_new, columns=['date', 'year', 'month'])
            X_new['predicted'] = regr.predict(X_new.drop('date', axis=1))
            X_new['category'] = [cat]*step
            dfs_new = dfs_new.append(X_new, ignore_index = True)

        df['predicted'] = predicted

        return {"new_sales": dfs_new.to_json(orient='split'), "old_sales": df.to_json(orient='split')}
    
    return redirect(url_for('login'))

if __name__ == '__main__':
    print('Server is running on localhost!')
    app.run(debug=True)