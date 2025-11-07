import json
import random
import datetime # <-- নতুন ইম্পোর্ট
import shortuuid # <-- নতুন ইম্পোর্ট
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_12345_replit'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://templates_o2y5_user:uKSnasMlaORMcq682TQCEkeQKtsUTVtB@dpg-d46l8dhr0fns73fp5dug-a/templates_o2y5'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- ডেটাবেস মডেল ---

class ExamSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    questions = db.relationship('Question', backref='exam_set', lazy=True, cascade="all, delete-orphan")

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)
    explanation = db.Column(db.String(1000), nullable=True)
    exam_set_id = db.Column(db.Integer, db.ForeignKey('exam_set.id'), nullable=False)

# --- নতুন ডেটাবেস মডেল: পরীক্ষার ফলাফল ---
class ExamResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # এটি হলো আপনার চাওয়া ইউনিক, শেয়ার করার মতো ID
    public_id = db.Column(db.String(22), unique=True, nullable=False, default=shortuuid.uuid)
    total_score = db.Column(db.Float, nullable=False)

    # আমরা প্রশ্নগুলোর ID এবং ফলাফলের লগ JSON স্ট্রিং হিসেবে সেভ করবো
    q_ids_json = db.Column(db.Text, nullable=False) # e.g., "[5, 8, 2]"
    results_log_json = db.Column(db.Text, nullable=False) # e.g., "{'5': {'points': 1.5}, ...}"

    exam_title = db.Column(db.String(300), nullable=True) # পরীক্ষার টাইটেল
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f'<ExamResult {self.public_id}>'

# --- রুট (Routes) ---

## 🏠 হোম পেজ (কোনো পরিবর্তন নেই)
@app.route('/')
def home():
    all_sets = ExamSet.query.order_by(ExamSet.id.desc()).all()
    total_questions = Question.query.count()
    return render_template('home.html', all_sets=all_sets, total_questions=total_questions)

## ➕ MCQ অ্যাড পেজ (সামান্য পরিবর্তন)
@app.route('/add', methods=['GET', 'POST'])
def add_mcq():
    if request.method == 'POST':
        # ... (JSON পার্সিং এবং ডেটাবেসে সেভ করার সব কোড আগের মতোই) ...
        json_data = request.form['json_data']
        try:
            data = json.loads(json_data)
            if 'title' not in data or not data['title']:
                 flash("Error: JSON must include a non-empty 'title' field.", "danger")
                 return redirect(url_for('add_mcq'))
            set_title = data['title']
            new_set = ExamSet(title=set_title)
            db.session.add(new_set)
            if 'questions' not in data or not data['questions']:
                flash("Error: JSON must include a 'questions' list.", "danger")
                return redirect(url_for('add_mcq'))
            for q_data in data['questions']:
                new_q = Question(
                    # ... (প্রশ্ন যোগ করার কোড) ...
                    question=q_data['question'],
                    option_a=q_data['options']['a'],
                    option_b=q_data['options']['b'],
                    option_c=q_data['options']['c'],
                    option_d=q_data['options']['d'],
                    correct_answer=q_data['correct_answer'],
                    explanation=q_data['explanation'],
                    exam_set=new_set
                )
                db.session.add(new_q)
            db.session.commit()
            new_questions_ids = [q.id for q in new_set.questions]

            # --- সেশন সেটআপ (সামান্য পরিবর্তন) ---
            session.clear()
            session['current_exam_qids'] = new_questions_ids
            session['total_score'] = 0
            session['exam_results'] = {}
            session['current_exam_title'] = set_title # <-- নতুন: পরীক্ষার টাইটেল সেশনে যোগ করা

            flash(f"New set '{set_title}' added. Exam started!", "success")
            return redirect(url_for('take_exam', q_index=0))
        except Exception as e:
            db.session.rollback()
            flash(f"Error processing JSON: {e}.", "danger")
            return redirect(url_for('add_mcq'))
    return render_template('add_mcq.html')


## 🚀 "Exam All" রুট (সামান্য পরিবর্তন)
@app.route('/start_exam_all')
def start_exam_all():
    all_q_ids = [q.id for q in Question.query.all()]
    if not all_q_ids:
        flash("No questions in database.", "warning")
        return redirect(url_for('home'))

    session.clear()
    session['current_exam_qids'] = all_q_ids
    session['total_score'] = 0
    session['exam_results'] = {}
    session['current_exam_title'] = "All Questions (Combined)" # <-- নতুন

    flash(f"Exam started with ALL {len(all_q_ids)} questions!", "info")
    return redirect(url_for('take_exam', q_index=0))


## ❌ ডিলিট রুট (কোনো পরিবর্তন নেই)
@app.route('/delete_set/<int:set_id>', methods=['POST'])
def delete_set(set_id):
    exam_set = ExamSet.query.get_or_404(set_id)
    try:
        db.session.delete(exam_set)
        db.session.commit()
        flash(f"Exam set '{exam_set.title}' has been deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting set: {e}", "danger")
    return redirect(url_for('home'))


## 🚀 নির্দিষ্ট সেট পরীক্ষা শুরু (সামান্য পরিবর্তন)
@app.route('/start_exam_set/<int:set_id>', methods=['POST'])
def start_exam_set(set_id):
    exam_set = ExamSet.query.get_or_404(set_id)
    q_ids = [q.id for q in Question.query.filter_by(exam_set_id=set_id).order_by(Question.id).all()]
    total_in_set = len(q_ids)

    if not q_ids:
        flash("This exam set has no questions.", "warning")
        return redirect(url_for('home'))

    # ... (ফর্ম থেকে অপশন প্রসেস করার সব কোড আগের মতোই) ...
    mode = request.form.get('mode', 'sequential')
    exam_type = request.form.get('exam_type', 'all')

    if exam_type == 'range':
        # ... (রেঞ্জ লজিক) ...
        range_input = request.form.get('range_input', '')
        try:
            start_str, end_str = range_input.split('-')
            start = int(start_str.strip())
            end = int(end_str.strip())
            if start < 1 or end > total_in_set or start > end:
                flash(f"Invalid range. Must be between 1 and {total_in_set}.", "danger")
                return redirect(url_for('home'))
            q_ids = q_ids[start-1:end]
        except ValueError:
            flash("Invalid range format. Use 'start-end'.", "danger")
            return redirect(url_for('home'))

    if mode == 'random':
        random.shuffle(q_ids)

    if exam_type == 'number':
        # ... (নাম্বার লজিক) ...
        try:
            number = int(request.form.get('number_input', '10'))
            if number <= 0:
                flash("Number must be greater than 0.", "danger")
                return redirect(url_for('home'))
            q_ids = q_ids[:number]
        except ValueError:
            flash("Invalid number entered.", "danger")
            return redirect(url_for('home'))

    # --- সেশন সেটআপ (সামান্য পরিবর্তন) ---
    session.clear()
    session['current_exam_qids'] = q_ids
    session['total_score'] = 0
    session['exam_results'] = {}
    session['current_exam_title'] = exam_set.title # <-- নতুন

    flash(f"Exam started for '{exam_set.title}' ({len(q_ids)} questions)", "info")
    return redirect(url_for('take_exam', q_index=0))


## 📝 মূল পরীক্ষার পেজ (সামান্য পরিবর্তন)
@app.route('/exam/<int:q_index>', methods=['GET', 'POST'])
def take_exam(q_index):
    if 'current_exam_qids' not in session:
        # ... (সেশন না পেলে হ্যান্ডেল করা) ...
        if request.method == 'GET':
            flash("Exam session not found. Please start again.", "danger")
            return redirect(url_for('home'))
        else:
            return jsonify({'error': 'Session expired'}), 400

    q_ids = session['current_exam_qids']

    # --- POST রিকোয়েস্ট (AJAX Call) ---
    if request.method == 'POST':
        # ... (POST-এর সব লজিক হুবহু আগের মতোই থাকবে) ...
        if q_index >= len(q_ids):
             return jsonify({'error': 'Exam finished'}), 400
        current_q_id = q_ids[q_index]
        question = Question.query.get(current_q_id)
        submitted_answer = request.form.get('option')
        if not submitted_answer:
            return jsonify({'error': 'No option selected'}), 400
        attempts_key = f'q_{current_q_id}_attempts'
        answered_key = f'q_{current_q_id}_answered'
        if session.get(answered_key, False):
            return jsonify({'error': 'Already answered'}), 400
        attempts = session.get(attempts_key, 0)
        if submitted_answer == question.correct_answer:
            points = max(0, 1.50 - (attempts * 0.50))
            session['total_score'] = session.get('total_score', 0) + points
            results_log = session.get('exam_results', {})
            results_log[str(current_q_id)] = {'points': points, 'attempts': attempts + 1}
            session['exam_results'] = results_log
            session[answered_key] = True
            session.pop(attempts_key, None)
            return jsonify({
                'status': 'correct',
                'points_earned': points,
                'total_score': session['total_score'],
                'potential_points': 0,
                'explanation': question.explanation
            })
        else:
            session[attempts_key] = attempts + 1
            disabled_options_key = f'q_{current_q_id}_disabled'
            disabled_options = session.get(disabled_options_key, [])
            if submitted_answer not in disabled_options:
                disabled_options.append(submitted_answer)
            session[disabled_options_key] = disabled_options
            new_potential = max(0, 1.50 - (session[attempts_key] * 0.50))
            return jsonify({
                'status': 'incorrect',
                'total_score': session.get('total_score', 0),
                'potential_points': new_potential,
                'disabled_option': submitted_answer
            })

    # --- GET রিকোয়েস্ট ---

    # --- গুরুত্বপূর্ণ পরিবর্তন: পরীক্ষা শেষ হলে ---
    if q_index >= len(q_ids):
        # এখন '/results'-এ না গিয়ে '/process_results'-এ যাবে
        return redirect(url_for('process_results'))

    # ... (GET রিকোয়েস্টের বাকি সব লজিক আগের মতোই থাকবে) ...
    current_q_id = q_ids[q_index]
    question = Question.query.get(current_q_id)
    if not question:
        flash(f"Question with ID {current_q_id} not found. Skipping.", "warning")
        return redirect(url_for('take_exam', q_index=q_index + 1))
    if q_index > 0:
        prev_q_id = q_ids[q_index - 1]
        session.pop(f'q_{prev_q_id}_answered', None)
        session.pop(f'q_{prev_q_id}_disabled', None)
    attempts_key = f'q_{current_q_id}_attempts'
    disabled_key = f'q_{current_q_id}_disabled'
    answered_key = f'q_{current_q_id}_answered'
    attempts = session.get(attempts_key, 0)
    disabled_options = session.get(disabled_key, [])
    potential_points = max(0, 1.50 - (attempts * 0.50))
    total_score = session.get('total_score', 0)
    show_explanation = session.get(answered_key, False)

    return render_template('exam.html',
                           question=question,
                           q_index=q_index,
                           total_questions=len(q_ids),
                           potential_points=potential_points,
                           disabled_options=disabled_options,
                           show_explanation=show_explanation,
                           total_score=total_score
                          )

## 📊 নতুন রুট: ফলাফল প্রসেস এবং সেভ করা
@app.route('/process_results')
def process_results():
    if 'current_exam_qids' not in session:
        flash("No results to process. Start an exam first.", "warning")
        return redirect(url_for('home'))

    # সেশন থেকে সব ডেটা সংগ্রহ করা
    total_score = session.get('total_score', 0)
    q_ids = session.get('current_exam_qids', [])
    exam_results_log = session.get('exam_results', {})
    exam_title = session.get('current_exam_title', 'Untitled Exam')

    try:
        # নতুন ExamResult অবজেক্ট তৈরি করা
        new_result = ExamResult(
            total_score=total_score,
            q_ids_json=json.dumps(q_ids), # লিস্ট-কে JSON স্ট্রিং-এ রূপান্তর
            results_log_json=json.dumps(exam_results_log), # ডিকশনারি-কে JSON স্ট্রিং-এ রূপান্তর
            exam_title=exam_title
        )
        db.session.add(new_result)
        db.session.commit()

        # সেভ করার পর আমরা ইউনিক public_id পাবো
        public_id = new_result.public_id

        # --- সেশন ক্লিয়ার করা ---
        session.pop('current_exam_qids', None)
        session.pop('total_score', None)
        session.pop('exam_results', None)
        session.pop('current_exam_title', None)
        for key in list(session.keys()):
            if key.startswith('q_'):
                session.pop(key)

        # নতুন পার্মানেন্ট রেজাল্ট পেজে রিডাইরেক্ট করা
        return redirect(url_for('view_result', public_id=public_id))

    except Exception as e:
        db.session.rollback()
        flash(f"Error saving results: {e}", "danger")
        return redirect(url_for('home'))


## 📊 নতুন রুট: সেভ করা ফলাফল দেখা
@app.route('/results/<string:public_id>')
def view_result(public_id):
    # ডেটাবেস থেকে public_id দিয়ে রেজাল্ট খোঁজা
    result = ExamResult.query.filter_by(public_id=public_id).first_or_404()

    # JSON স্ট্রিং থেকে ডেটা পার্স করা
    total_score = result.total_score
    q_ids = json.loads(result.q_ids_json)
    exam_results_log = json.loads(result.results_log_json)
    exam_title = result.exam_title

    # results.html টেমপ্লেটের জন্য full_results লিস্ট তৈরি করা
    full_results = []
    for q_id in q_ids:
        question = Question.query.get(q_id)
        if question:
            # JSON-এ কী (key) সবসময় স্ট্রিং হয়, তাই str(q_id) ব্যবহার
            result_data = exam_results_log.get(str(q_id), {'points': 0, 'attempts': 0})
            full_results.append({
                'question': question,
                'result': result_data
            })

    # টেমপ্লেট রেন্ডার করা
    return render_template('results.html', 
                           total_score=total_score,
                           full_results=full_results,
                           exam_title=exam_title) # <-- নতুন: টাইটেল পাঠানো


## 📊 পুরনো /results রুটটি এখন আর ব্যবহৃত হবে না, তাই মুছে ফেলা হলো।


# --- অ্যাপ রান করা ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # ExamResult টেবিল তৈরি করবে
    app.run(host='0.0.0.0', port=8080)


