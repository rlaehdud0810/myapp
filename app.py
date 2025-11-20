from flask import Flask, render_template, request, redirect, session, url_for
import json, os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'replace-this-with-a-secure-random-string'

DATA_FILE = 'users.json'

# ----------------- 데이터 처리 -----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        data = {"users": {}, "admin": {"id":"admin", "pw":generate_password_hash("admin")}}
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ----------------- 통계 계산 -----------------
def calculate_metrics(results):
    diag_set = set(v['true'] for v in results)
    metrics = {}
    for d in diag_set:
        TP = sum(1 for v in results if v['true']==d and v['pred']==d)
        FN = sum(1 for v in results if v['true']==d and v['pred']!=d)
        TN = sum(1 for v in results if v['true']!=d and v['pred']!=d)
        FP = sum(1 for v in results if v['true']!=d and v['pred']==d)
        sens = TP/(TP+FN) if TP+FN>0 else None
        spec = TN/(TN+FP) if TN+FP>0 else None
        ppv = TP/(TP+FP) if TP+FP>0 else None
        npv = TN/(TN+FN) if TN+FN>0 else None
        metrics[d] = {
            "TP":TP,"FN":FN,"FP":FP,"TN":TN,
            "Sensitivity":sens,"Specificity":spec,
            "PPV":ppv,"NPV":npv
        }
    return metrics

# ----------------- Quiz 문제 -----------------
questions = [
    {
        "images": [
            "images/1a.jpg",
            "images/1b.jpg",
            "images/1c.jpg"
        ],
        "true": "Normal"
    },
    {
        "images": [
            "images/2a.jpg",
            "images/2b.jpg"
        ],
        "true": "Glaucoma"
    }
]

# ----------------- Routes -----------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    data = load_data()
    if request.method=='POST':
        uid = request.form['uid'].strip()
        pw = request.form['pw'].strip()
        if not uid or not pw:
            return render_template('register.html', error="ID와 PW 입력 필요")
        if uid in data['users']:
            return render_template('register.html', error="이미 존재하는 사용자")
        data['users'][uid] = {"pw":generate_password_hash(pw), "results":[]}
        save_data(data)
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    data = load_data()
    if request.method=='POST':
        uid = request.form['uid']
        pw = request.form['pw']
        if uid=='admin' and check_password_hash(data['admin']['pw'], pw):
            session.clear()
            session['admin'] = True
            return redirect(url_for('admin'))
        if uid in data['users'] and check_password_hash(data['users'][uid]['pw'], pw):
            session.clear()
            session['uid'] = uid
            session['q_index'] = 0
            session['answers'] = []
            return redirect(url_for('quiz'))
        return render_template('login.html', error="로그인 실패")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/quiz', methods=['GET','POST'])
def quiz():
    if 'uid' not in session:
        return redirect(url_for('login'))

    if 'q_index' not in session:
        session['q_index'] = 0
    if 'answers' not in session:
        session['answers'] = []

    q_index = session['q_index']

    # 모든 문제 완료
    if q_index >= len(questions):
        data = load_data()
        data['users'][session['uid']]['results'].append(session['answers'].copy())
        save_data(data)
        session.pop('q_index')
        session.pop('answers')
        return redirect(url_for('result_user'))

    question = questions[q_index]

    if request.method == 'POST':
        action = request.form.get('action', 'next')

        if action == 'next':
            pred = request.form.get('answer', '')
            if len(session['answers']) > q_index:
                session['answers'][q_index] = {"true": question['true'], "pred": pred}
            elif len(session['answers']) == q_index:
                session['answers'].append({"true": question['true'], "pred": pred})
            session['q_index'] += 1
        elif action == 'prev' and q_index > 0:
            session['q_index'] -= 1

        return redirect(url_for('quiz'))

    return render_template('quiz.html', question=question, q_index=q_index+1, total=len(questions))

@app.route('/result_user')
def result_user():
    if 'uid' not in session:
        return redirect(url_for('login'))
    uid = session['uid']
    data = load_data()
    latest = data['users'][uid]['results'][-1]
    total_correct = sum(1 for v in latest if v['true']==v['pred'])
    total = len(latest)
    accuracy = total_correct / total * 100 if total>0 else 0
    return render_template('result_user.html', accuracy=accuracy, total=total, correct=total_correct)

@app.route('/admin')
def admin():
    if 'admin' not in session:
        return redirect(url_for('login'))
    data = load_data()
    stats = {}
    for uid, info in data['users'].items():
        if uid == 'admin':
            continue
        if info['results']:
            last_result = info['results'][-1]
            flat_result = [r for r in last_result]
            stats[uid] = calculate_metrics(flat_result)
        else:
            stats[uid] = {}
    return render_template('admin.html', stats=stats)

@app.route('/delete_user/<uid>', methods=['POST'])
def delete_user(uid):
    if 'admin' not in session:
        return redirect(url_for('login'))
    data = load_data()
    if uid in data['users']:
        del data['users'][uid]
        save_data(data)
    return redirect(url_for('admin'))

# ----------------- Render 포트 대응 -----------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
