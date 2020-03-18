from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, IntegerField, validators
from passlib.hash import sha256_crypt
from functools import wraps
from werkzeug.utils import secure_filename
import pycountry,os,subprocess
import joblib
import pandas as pd
import lightgbm as lgb
import numpy as np

app = Flask(__name__)

#Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Vired17DIL'
app.config['MYSQL_DB'] = 'project'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

#Questions folder
UPLOAD_QUESTIONS_FOLDER = 'E:/main_project/questions_folder'
USER_SUBMISSIONS_FOLDER = 'E:/main_project/user_submissions'

#init MYSQL
mysql = MySQL(app)

#Register Form Class
class RegisterForm(Form):
    name = StringField('Name', [
        validators.DataRequired(),
        validators.Length(min = 1, max=50)
        ])
    email = StringField('Email',[
        validators.DataRequired(),
        validators.Length(min = 6, max= 50)
        ])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
        ])
    confirm = PasswordField('Confirm Password',[validators.DataRequired()])
    submission_count = StringField('Submission Count',[
        validators.DataRequired()
    ])
    problem_solved = StringField('Problem Solved',[
        validators.DataRequired()
    ])
    contribution = StringField('Contribution',[
        validators.DataRequired()
    ])
    follower_count = StringField('Follower Count',[
        validators.DataRequired()
    ])
    max_rating = StringField('Max Rating',[
        validators.DataRequired()
    ])
    rating = StringField('Rating',[
        validators.DataRequired()
    ])
    user_rank = StringField('User Rank',[
        validators.DataRequired()
    ])

#User register
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        password = sha256_crypt.hash(str(form.password.data))
        country = request.form['co']
        print(country)
        submission_count = form.submission_count.data
        problem_solved = form.problem_solved.data
        contribution = form.contribution.data
        follower_count = form.follower_count.data
        max_rating = form.max_rating.data
        rating = form.rating.data
        user_rank = form.user_rank.data


        #Create Cursor
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users(name,email,password,country,submission_count,problem_solved,contribution,follower_count,max_rating,rating,user_rank) VALUES(%s , %s , %s, %s,%s , %s , %s, %s,%s , %s , %s)",(name, email, password, country,submission_count,problem_solved,contribution,follower_count,max_rating,rating,user_rank))
        #Commit to DB
        mysql.connection.commit()
        #Close connection
        cur.close()

        flash('You are now registered and can log in', 'success')
        return redirect(url_for('home'))

    #Country field
    co = [country.name for country in pycountry.countries]
    return render_template('register.html', form=form, co=co)

@app.route('/')
def home():
    return render_template('home.html')

# User Login
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        #Get form fields
        email = request.form['email']
        password_candidate = request.form['password']

        # Create cursor
        cur = mysql.connection.cursor()
        #Get user by Email
        result = cur.execute("SELECT * FROM users WHERE email = %s",[email])

        if result > 0:
            #Get stored hash
            data  = cur.fetchone()
            password = data['password']

            #compare passwords
            if sha256_crypt.verify(password_candidate,password):
                #Passed
                session['logged_in'] = True
                session['email'] = email

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                app.logger.info('PASSWORD NOT MATCHED')
                error = 'PASSWORD NOT MATCHED'
                return render_template('login.html',error=error)\
            #Close connection
            cur.close()
        else:
            app.logger.info('NO USER')
            error = "User not found"
            return render_template('login.html',error=error)

    return render_template('login.html')

#Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please Login','danger')
            return redirect(url_for('login'))
    return wrap

#Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@is_logged_in
def dashboard():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM users WHERE email = %s",[session['email']])

    if result>0:
        user = cur.fetchone()
        return render_template('dashboard.html', user=user)
    else:
        msg='No User Found'
        return render_template('dashboard.html', msg = msg)
    cur.close()




# class ProblemForm(Form):
#     title = StringField('Title', [validators.Length(min=1, max=200)])
#     #body = TextAreaField('Body', [validators.Length(min=30)])
#     level_type = StringField('Level',[validators.Length(min=1,max=20)])
#     points = IntegerField('Points',[validators.DataRequired()])
#     tags = StringField('Tags',[validators.Length(min = 2, max = 100)])
#
# @app.route('/add_problem', methods=['GET','POST'])
# @is_logged_in
# def add_problem():
#     form = ProblemForm(request.form)
#     if request.method == 'POST' and form.validate():
#         title = form.title.data
#         #body = form.body.data
#         level_type = form.level_type.data
#         points = form.points.data
#         tags = form.tags.data
#
#         #TODO: Save file to questions folder and save path in db.
#         #Create cursor
#         cur = mysql.connection.cursor()
#         #Execute
#         cur.execute("INSERT INTO questions(title,level_type,points,tags) VALUES(%s, %s, %s, %s)",(title,level_type,points,tags))
#         #Commit to DB
#         mysql.connection.commit()
#         #Close connnection
#         cur.close()
#
#         flash('Problem Created','success')
#         return redirect(url_for('dashboard'))
#     return render_template('add_problem.html',form = form)

@app.route('/problems')
def problems():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM questions")
    problems = cur.fetchall()

    ##Step-1: Take each individual problem and get the prediction
    predict_results = predict()

    ##Step-2: Values that are [1,2,3] must be Recommended
    avg = sum(predict_results)/len(predict_results)
    l=[]
    for i in predict_results:
        check = i/avg
        print('$'*50)
        print('$'*50)
        print('check: ',check)
        print('$'*50)
        print('$'*50)
        if i/avg < 1:
            l.append(i)
        else:
            l.append(0)

    ##Step-3: Provide a button that redirects to the problem page


    if result>0:
        return render_template('problems.html', problems=problems,predict_results=l)
    else:
        msg='No Problems Found'
        return render_template('problems.html', msg = msg)
    cur.close()

def predict():
    predict_results = []
    cur = mysql.connection.cursor()
    users = cur.execute("SELECT * FROM users WHERE email = %s",[session['email']])
    users_data = cur.fetchone()
    question = cur.execute("SELECT * FROM questions")
    all_questions = cur.fetchall()
    print('#'*50)
    print('#'*50)
    print('#'*50)
    print(all_questions)
    print('#'*50)
    print('#'*50)
    cur.close()
    print(users_data)
    print('*************************************************************************')
    for question_data in all_questions:
        print(question_data)
        user_data = pd.DataFrame([users_data])
        question_data = pd.DataFrame([question_data])
        train_data = pd.concat([user_data,question_data],axis = 1)
        train_data = train_data.drop(['user_id','email','password','title'],axis = 1)
        print('*'*50)
        train_data.rename(columns = {'name':'user_id','user_rank':'rank'},inplace = True)
        train_data['last_online_time_seconds'] = (train_data['last_online_time_seconds']-
                                            pd.Timestamp("1970-01-01")) // pd.Timedelta('1s')
        train_data['registration_time_seconds'] = (train_data['registration_time_seconds']-
                                            pd.Timestamp("1970-01-01")) // pd.Timedelta('1s')
        train_data['problem_id'] = 'prob_'+str(train_data['problem_id'])
        train_data['problem_id'] = train_data['problem_id'].astype(object)
        train_data['user_id'] = train_data['user_id'].astype(object)
        train_data['submission_count'] = train_data['submission_count'].astype(int)
        train_data['problem_solved'] = train_data['problem_solved'].astype(int)
        train_data['contribution'] = train_data['contribution'].astype(int)
        train_data['follower_count'] = train_data['follower_count'].astype(int)
        train_data['last_online_time_seconds'] = train_data['last_online_time_seconds'].astype(int)
        train_data['registration_time_seconds'] = train_data['registration_time_seconds'].astype(int)
        train_data['country'] = train_data['country'].astype(object)
        train_data['rank'] = train_data['rank'].astype(object)
        train_data['level_type'] = train_data['level_type'].astype(object)
        train_data['tags'] = train_data['tags'].astype(object)
        train_data['max_rating'] = train_data['max_rating'].astype(float)
        train_data['rating'] = train_data['rating'].astype(float)
        train_data['points'] = train_data['points'].astype(float)
        print(train_data.dtypes)

        #First
        train_data['seconds'] = (train_data['last_online_time_seconds'].values)%(24 * 3600)
        train_data['hour'] = (train_data['seconds'].values)//3600
        train_data['seconds'] = (train_data['seconds'].values)%3600
        train_data['minutes'] = (train_data['seconds'].values)//60
        train_data['seconds'] = (train_data['seconds'].values)%60


        train_data['reg_seconds'] = (train_data['registration_time_seconds'].values)%(24 * 3600)
        train_data['reg_hour'] = (train_data['reg_seconds'].values)//3600
        train_data['reg_seconds'] = (train_data['reg_seconds'].values)%3600
        train_data['reg_minutes'] = (train_data['reg_seconds'].values)//60
        train_data['reg_seconds'] = (train_data['reg_seconds'].values)%60


        train_data['days_active']=(train_data['last_online_time_seconds']-train_data['registration_time_seconds'])/(60*60*24)
        train_data['weeks_active'] = train_data['days_active']/7
        train_data['months_active'] = train_data['days_active']/30
        train_data['years_active'] = train_data['days_active']/365
        train_data['submissions per day'] = train_data['submission_count']/train_data['days_active']
        train_data['submissions per week'] = train_data['submission_count']/train_data['weeks_active']
        train_data['submissions per month'] = train_data['submission_count']/train_data['months_active']
        train_data['submissions per year'] = train_data['submission_count']/train_data['years_active']


        train_data['problem_solved per day'] = train_data['problem_solved']/train_data['days_active']
        train_data['problem_solved per week'] = train_data['problem_solved']/train_data['weeks_active']
        train_data['problem_solved per month'] = train_data['problem_solved']/train_data['months_active']
        train_data['problem_solved per year'] = train_data['problem_solved']/train_data['years_active']


        train_data['decresed rating'] = train_data['max_rating']-train_data['rating']
        train_data['rating ratio'] = train_data['rating']/train_data['max_rating']


        train_data['max rating to points ratio'] = train_data['max_rating']/train_data['points']
        train_data['rating to points ratio'] = train_data['rating']/train_data['points']


        #followers features
        train_data['submissions per follower'] = train_data['submission_count']/(train_data['follower_count']+1)
        train_data['problem_solved per follower'] = train_data['problem_solved']/(train_data['follower_count']+1)
        train_data['contribution per follower'] = train_data['contribution']/(train_data['follower_count']+1)
        train_data['follwers per day'] = train_data['follower_count']/train_data['days_active']
        train_data['follwers per week'] = train_data['follower_count']/train_data['weeks_active']
        train_data['follwers per month'] = train_data['follower_count']/train_data['months_active']
        train_data['follwers per year'] = train_data['follower_count']/train_data['years_active']


        #contributions features
        train_data['contribution per day'] = train_data['contribution']/train_data['days_active']
        train_data['contribution per week'] = train_data['contribution']/train_data['weeks_active']
        train_data['contribution per month'] = train_data['contribution']/train_data['months_active']
        train_data['contribution per year'] = train_data['contribution']/train_data['years_active']

        #rating features
        train_data['rating per problem'] = train_data['rating']/train_data['problem_solved']
        train_data['submission per problem'] = train_data['rating']/train_data['submission_count']
        train_data['max rating per problem'] = train_data['max_rating']/train_data['problem_solved']
        train_data['max submission per problem'] = train_data['max_rating']/train_data['submission_count']

        def get_new_columns(name,aggs):
            return [name + '_' + k + '_' + agg for k in aggs.keys() for agg in aggs[k]]
        aggs = {}
        for col in ['problem_id','country','rank','level_type','tags']:
            aggs[col] = ['nunique','count']
        aggs['submission_count'] = ['sum','max','min','mean']
        aggs['problem_solved'] = ['sum','max','min','mean']
        aggs['contribution'] = ['sum','max','min','mean']
        aggs['follower_count'] = ['sum','max','min','mean']
        aggs['max_rating'] = ['max','min','mean']
        aggs['rating'] = ['max','min','mean']
        aggs['weeks_active'] = ['sum','max','min','mean']
        aggs['months_active'] = ['sum','max','min','mean']
        aggs['years_active'] =  ['sum','max','min','mean']
        aggs['days_active']= ['sum','max','min','mean']
        new_columns = get_new_columns('user',aggs)
        all_data_brach = train_data.groupby('user_id').agg(aggs)
        all_data_brach.columns = new_columns
        all_data_brach.reset_index(drop=False,inplace=True)
        train_data = train_data.merge(all_data_brach,on='user_id',how='left')

        def get_new_columns(name,aggs):
            return [name + '_' + k + '_' + agg for k in aggs.keys() for agg in aggs[k]]
        aggs = {}
        for col in ['user_id','country','rank','level_type','tags']:
            aggs[col] = ['nunique','count']
        aggs['submission_count'] = ['sum','max','min','mean']
        aggs['problem_solved'] = ['sum','max','min','mean']
        aggs['contribution'] = ['sum','max','min','mean']
        aggs['follower_count'] = ['sum','max','min','mean']
        aggs['max_rating'] = ['max','min','mean']
        aggs['rating'] = ['max','min','mean']
        aggs['weeks_active'] = ['sum','max','min','mean']
        aggs['months_active'] = ['sum','max','min','mean']
        aggs['years_active'] =  ['sum','max','min','mean']
        aggs['days_active']= ['sum','max','min','mean']
        new_columns = get_new_columns('problem',aggs)
        all_data_brach = train_data.groupby('problem_id').agg(aggs)
        all_data_brach.columns = new_columns
        all_data_brach.reset_index(drop=False,inplace=True)
        train_data = train_data.merge(all_data_brach,on='problem_id',how='left')

        def get_new_columns(name,aggs):
            return [name + '_' + k + '_' + agg for k in aggs.keys() for agg in aggs[k]]
        aggs = {}
        for col in ['problem_id','rank','level_type','tags']:
            aggs[col] = ['nunique','count']
        aggs['submission_count'] = ['sum','max','min','mean']
        aggs['problem_solved'] = ['sum','max','min','mean']
        aggs['contribution'] = ['sum','max','min','mean']
        aggs['follower_count'] = ['sum','max','min','mean']
        aggs['max_rating'] = ['max','min','mean']
        aggs['rating'] = ['max','min','mean']
        aggs['weeks_active'] = ['sum','max','min','mean']
        aggs['months_active'] = ['sum','max','min','mean']
        aggs['years_active'] =  ['sum','max','min','mean']
        aggs['days_active']= ['sum','max','min','mean']
        new_columns = get_new_columns('country',aggs)
        all_data_brach = train_data.groupby('country').agg(aggs)
        all_data_brach.columns = new_columns
        all_data_brach.reset_index(drop=False,inplace=True)
        train_data = train_data.merge(all_data_brach,on='country',how='left')

        def get_new_columns(name,aggs):
            return [name + '_' + k + '_' + agg for k in aggs.keys() for agg in aggs[k]]
        aggs = {}
        for col in ['problem_id','country','level_type','tags']:
            aggs[col] = ['nunique','count']
        aggs['submission_count'] = ['sum','max','min','mean']
        aggs['problem_solved'] = ['sum','max','min','mean']
        aggs['contribution'] = ['sum','max','min','mean']
        aggs['follower_count'] = ['sum','max','min','mean']
        aggs['max_rating'] = ['max','min','mean']
        aggs['rating'] = ['max','min','mean']
        aggs['weeks_active'] = ['sum','max','min','mean']
        aggs['months_active'] = ['sum','max','min','mean']
        aggs['years_active'] =  ['sum','max','min','mean']
        aggs['days_active']= ['sum','max','min','mean']
        new_columns = get_new_columns('rank',aggs)
        all_data_brach = train_data.groupby('rank').agg(aggs)
        all_data_brach.columns = new_columns
        all_data_brach.reset_index(drop=False,inplace=True)
        train_data = train_data.merge(all_data_brach,on='rank',how='left')

        def get_new_columns(name,aggs):
            return [name + '_' + k + '_' + agg for k in aggs.keys() for agg in aggs[k]]
        aggs = {}
        for col in ['problem_id','country','rank','tags']:
            aggs[col] = ['nunique','count']
        aggs['submission_count'] = ['sum','max','min','mean']
        aggs['problem_solved'] = ['sum','max','min','mean']
        aggs['contribution'] = ['sum','max','min','mean']
        aggs['follower_count'] = ['sum','max','min','mean']
        aggs['max_rating'] = ['max','min','mean']
        aggs['rating'] = ['max','min','mean']
        aggs['weeks_active'] = ['sum','max','min','mean']
        aggs['months_active'] = ['sum','max','min','mean']
        aggs['years_active'] =  ['sum','max','min','mean']
        aggs['days_active']= ['sum','max','min','mean']
        new_columns = get_new_columns('level',aggs)
        all_data_brach = train_data.groupby('level_type').agg(aggs)
        all_data_brach.columns = new_columns
        all_data_brach.reset_index(drop=False,inplace=True)
        train_data = train_data.merge(all_data_brach,on='level_type',how='left')

        def get_new_columns(name,aggs):
            return [name + '_' + k + '_' + agg for k in aggs.keys() for agg in aggs[k]]
        aggs = {}
        for col in ['problem_id','country','rank','level_type']:
            aggs[col] = ['nunique','count']
        aggs['submission_count'] = ['sum','max','min','mean']
        aggs['problem_solved'] = ['sum','max','min','mean']
        aggs['contribution'] = ['sum','max','min','mean']
        aggs['follower_count'] = ['sum','max','min','mean']
        aggs['max_rating'] = ['max','min','mean']
        aggs['rating'] = ['max','min','mean']
        aggs['weeks_active'] = ['sum','max','min','mean']
        aggs['months_active'] = ['sum','max','min','mean']
        aggs['years_active'] =  ['sum','max','min','mean']
        aggs['days_active']= ['sum','max','min','mean']
        new_columns = get_new_columns('tags',aggs)
        all_data_brach = train_data.groupby('tags').agg(aggs)
        all_data_brach.columns = new_columns
        all_data_brach.reset_index(drop=False,inplace=True)
        train_data = train_data.merge(all_data_brach,on='tags',how='left')

        for col in ['user_id', 'problem_id', 'country','tags']:
            train_data[col] = train_data[col].apply( lambda x: hash(str(x)) % 5000)

        from sklearn.preprocessing import LabelEncoder
        from sklearn import preprocessing
        # Label Encoding
        for f in ['level_type', 'rank']:
            if train_data[f].dtype=='object':
                lbl = preprocessing.LabelEncoder()
                lbl.fit(list(train_data[f].values))
                train_data[f] = lbl.transform(list(train_data[f].values))

        gbm_pickle = joblib.load('lgb_model.pkl')
        print("Model loaded successfully")
        y_pred = gbm_pickle.predict(train_data,num_iteration = gbm_pickle.best_iteration)
        from collections import Counter
        def eval_f1_lgb_regr(y_pred):
            label_smoothing_factor = 1.7133
            dist = Counter({1: 82804, 2: 47320, 3: 14143, 4: 5499, 6: 3033, 5: 2496})
            for k in dist:
                dist[k] /= 155295
            #train_data['attempts_range'].hist()

            acum = 0
            bound = {}
            for i in range(6):
                acum += dist[i]
                bound[i] = np.percentile(y_pred, acum * 100)

            def classify(x):
                if x <= bound[1]:
                    return 1
                elif x > bound[0] and x < bound[1]:
                    return 1
                elif x > bound[1] and x < bound[2]:
                    return 2
                elif x > bound[2] and x < bound[3]:
                    return 3
                elif x > bound[3] and x < bound[4]:
                    return 4
                elif x >bound[4] and x < bound[5]:
                    return 5
                else:
                    return 6

            y_pred = list(map(classify, y_pred))
            #print('accuracy score:',accuracy_score(y_true,y_pred))
            #print('recall score: ',max(recall_score(y_true,y_pred,average=None)))

            return y_pred
        print(y_pred)
        print('-'*50)
        result = eval_f1_lgb_regr(y_pred) #Result from ML Model
        print(result)
        predict_results.append(y_pred)
        # if result[0] >= 1:
        #         output = "Recommended"
        #         return render_template('submit.html',output=output)
    return predict_results


@app.route('/problem/<string:id>/')
def problem(id):
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM questions WHERE title = %s",[id])
    #print(result)
    problem = cur.fetchone()
    #Get file
    filepath = os.path.join(UPLOAD_QUESTIONS_FOLDER,id+'.txt')
    data = open(filepath,'r+')
    content = data.read()
    data.close()
    return render_template('problem.html', problem=problem,content=content)

@app.route('/problem/<string:id>/getFile',methods=['GET','POST'])
def getFile(id):
    if request.files['myfile'].filename != '':
        if request.method == 'POST':
            file = request.files['myfile']
            ## Save file with file ID in database
            problem = id
            email = session['email']
            #Cursor
            cur = mysql.connection.cursor()
            #Save to DB
            cur.execute("INSERT INTO submissions(email,result,problem) VALUES(%s, %s, %s)",[email,1,problem])
            mysql.connection.commit()
            #File id
            file_id = cur.lastrowid


            filename = secure_filename(file.filename)
            path = str(file_id)+'.py'
            fp = os.path.join(USER_SUBMISSIONS_FOLDER, path)
            file.save(fp)
            #Later, change result to compiled and run file.
            try:
                output = subprocess.check_output(['python',fp])
                ans = output.decode('utf-8')
                code = 0
                result = code
                #Update DB
                print("Success result: ",result)
                print("file_id: ",file_id)
                cur.execute("UPDATE submissions SET  result = %s WHERE id = %s",(0,file_id))
                mysql.connection.commit()
                print("Success update")


                flash('Submitted','success')
                return render_template('submit.html',output=ans,error=code)
            except subprocess.CalledProcessError as call:
                output = call.output.decode('utf-8')
                code = call.returncode
                result = code
                #Update DB
                print("Failed result: ",result)
                print("file_id: ",file_id)
                cur.execute("UPDATE submissions SET result = %s WHERE id = %s",(1,file_id))
                mysql.connection.commit()
                print("Failure update")
                cur.close()
                if(code != 0):
                    error = 'Error'
                flash('Error','danger')
                return render_template('submit.html', output=output, error=error)
            msg = "File submited"

            # #Code for prediction
            # cur = mysql.connection.cursor()
            # users = cur.execute("SELECT * FROM users WHERE email = %s",[session['email']])
            #
            # #Converting users to Pandas DataFrame
            # data = pd.DataFrame([users])


    else:
        msg = "No File submitted"
    return render_template('submit.html',msg=msg)



if __name__ == '__main__':
    app.secret_key = 'megatron123'
    app.run(debug=True)
