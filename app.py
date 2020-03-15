from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, IntegerField, validators
from passlib.hash import sha256_crypt
from functools import wraps
from werkzeug.utils import secure_filename
import pycountry,os,subprocess

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
        #Create Cursor
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users(name,email,password,country) VALUES(%s , %s , %s, %s)",(name, email, password, country))
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
    if result>0:
        return render_template('problems.html', problems=problems)
    else:
        msg='No Problems Found'
        return render_template('problems.html', msg = msg)
    cur.close()

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
                cur.close()
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
    else:
        msg = "No File submitted"
    return render_template('submit.html',msg=msg)




if __name__ == '__main__':
    app.secret_key = 'megatron123'
    app.run(debug=True)
