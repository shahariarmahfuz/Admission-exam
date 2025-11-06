import json
import random # <-- নতুন ইম্পোর্ট
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_12345_replit'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mcq_app.db'
db = SQLAlchemy(app)

# --- ডেটাবেস মডেল (কোনো পরিবর্তন নেই) ---
class ExamSet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    questions = db.relationship('Question', backref='exam_set', lazy=True, cascade="all, delete-orphan")

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    # ... (বাকি কলামগুলো যেমন ছিল)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)
    explanation = db.Column(db.String(1000), nullable=True)
    exam_set_id = db.Column(db.Integer, db.ForeignKey('exam_set.id'), nullable=False)

# --- রুট (Routes) ---

## 🏠 হোম পেজ (কোনো পরিবর্তন নেই)
@app.route('/')
def home():
    all_sets = ExamSet.query.order_by(ExamSet.id.desc()).all()
    total_questions = Question.query.count()
    return render_template('home.html', all_sets=all_sets, total_questions=total_questions)

## ➕ MCQ অ্যাড পেজ (কোনো পরিবর্তন নেই)
@app.route('/add', methods=['GET', 'POST'])
def add_mcq():
    # ... (এই কোডটি আগের মতোই থাকবে)
    if request.method == 'POST':
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
            session.clear()
            session['current_exam_qids'] = new_questions_ids
            session['total_score'] = 0
            session['exam_results'] = {}
            flash(f"New set '{set_title}' with {len(new_questions_ids)} questions added. Exam started!", "success")
            return redirect(url_for('take_exam', q_index=0))
        except Exception as e:
            db.session.rollback()
            flash(f"Error processing JSON: {e}. Make sure JSON format is correct.", "danger")
            return redirect(url_for('add_mcq'))
    return render_template('add_mcq.html')


## 🚀 "Exam All" রুট (কোনো পরিবর্তন নেই)
@app.route('/start_exam_all')
def start_exam_all():
    # ... (এই কোডটি আগের মতোই থাকবে)
    all_q_ids = [q.id for q in Question.query.all()]
    if not all_q_ids:
        flash("No questions in the database to start an exam.", "warning")
        return redirect(url_for('home'))
    session.clear()
    session['current_exam_qids'] = all_q_ids
    session['total_score'] = 0
    session['exam_results'] = {}
    flash(f"Exam started with ALL {len(all_q_ids)} questions!", "info")
    return redirect(url_for('take_exam', q_index=0))


## ❌ নতুন রুট: জোট (Set) ডিলিট করা
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


## 🚀 নতুন রুট: নির্দিষ্ট সেট পরীক্ষা শুরু (অনেক পরিবর্তন)
@app.route('/start_exam_set/<int:set_id>', methods=['POST'])
def start_exam_set(set_id):
    exam_set = ExamSet.query.get_or_404(set_id)

    # প্রশ্নগুলোর ID সংগ্রহ করা (অর্ডার ঠিক রেখে)
    # আমরা Question.id অনুযায়ী অর্ডার করছি ডিফল্ট হিসেবে
    q_ids = [q.id for q in Question.query.filter_by(exam_set_id=set_id).order_by(Question.id).all()]
    total_in_set = len(q_ids)

    if not q_ids:
        flash("This exam set has no questions.", "warning")
        return redirect(url_for('home'))

    # --- ফর্ম থেকে অপশনগুলো নেওয়া ---
    mode = request.form.get('mode', 'sequential') # sequential vs random
    exam_type = request.form.get('exam_type', 'all') # all vs number vs range

    # --- লজিক ১: রেঞ্জ (Range) অনুযায়ী ফিল্টার ---
    if exam_type == 'range':
        range_input = request.form.get('range_input', '')
        try:
            start_str, end_str = range_input.split('-')
            start = int(start_str.strip())
            end = int(end_str.strip())

            if start < 1 or end > total_in_set or start > end:
                flash(f"Invalid range. Must be between 1 and {total_in_set}.", "danger")
                return redirect(url_for('home'))

            # 1-based ইনডেক্স থেকে 0-based ইনডেক্সে রূপান্তর
            q_ids = q_ids[start-1:end] # e.g., 23-34 means index 22 to 33

        except ValueError:
            flash("Invalid range format. Use 'start-end' (e.g., '23-34').", "danger")
            return redirect(url_for('home'))

    # --- লজিক ২: র‍্যান্ডমাইজ (Shuffle) ---
    if mode == 'random':
        random.shuffle(q_ids)

    # --- লজিক ৩: নির্দিষ্ট সংখ্যা (Number) ---
    if exam_type == 'number':
        try:
            number = int(request.form.get('number_input', '10'))
            if number <= 0:
                flash("Number must be greater than 0.", "danger")
                return redirect(url_for('home'))

            # যদি র‍্যান্ডম হয়, তাহলে শাফল করা লিস্ট থেকে প্রথম N টি নেবে
            # যদি র‍্যান্ডম না হয়, তাহলে প্রথম N টি নেবে
            q_ids = q_ids[:number]

        except ValueError:
            flash("Invalid number entered.", "danger")
            return redirect(url_for('home'))

    # --- পরীক্ষা শুরু করা ---
    session.clear()
    session['current_exam_qids'] = q_ids
    session['total_score'] = 0
    session['exam_results'] = {}

    flash(f"Exam started for '{exam_set.title}' ({len(q_ids)} questions)", "info")
    return redirect(url_for('take_exam', q_index=0))


# --- এই রুটগুলোতে কোনো পরিবর্তন দরকার নেই ---
# ... (take_exam এবং results ফাংশন আগের মতোই থাকবে) ...
@app.route('/exam/<int:q_index>', methods=['GET', 'POST'])
def take_exam(q_index):
    if 'current_exam_qids' not in session:
        if request.method == 'GET':
            flash("Exam session not found. Please start again.", "danger")
            return redirect(url_for('home'))
        else:
            return jsonify({'error': 'Session expired'}), 400

    q_ids = session['current_exam_qids']

    # --- POST রিকোয়েস্ট (AJAX Call) ---
    if request.method == 'POST':
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
    if q_index >= len(q_ids):
        return redirect(url_for('results'))

    current_q_id = q_ids[q_index]
    question = Question.query.get(current_q_id)

    if not question:
        flash(f"Question with ID {current_q_id} not found. Skipping.", "warning")
        return redirect(url_for('take_exam', q_index=q_index + 1))

    # পরবর্তী প্রশ্নে যাওয়ার আগে আগের প্রশ্নের 'answered' ফ্ল্যাগ মুছে ফেলা
    if q_index > 0:
        prev_q_id = q_ids[q_index - 1]
        session.pop(f'q_{prev_q_id}_answered', None)

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

@app.route('/results')
def results():
    # ... (এই কোডটি আগের মতোই থাকবে)
    if 'current_exam_qids' not in session:
        flash("No results to display. Start an exam first.", "warning")
        return redirect(url_for('home'))
    total_score = session.get('total_score', 0)
    q_ids = session.get('current_exam_qids', [])
    exam_results_log = session.get('exam_results', {})
    full_results = []
    for q_id in q_ids:
        question = Question.query.get(q_id)
        if question:
            result_data = exam_results_log.get(str(q_id), {'points': 0, 'attempts': 0})
            full_results.append({
                'question': question,
                'result': result_data
            })
    session.pop('current_exam_qids', None)
    session.pop('total_score', None)
    session.pop('exam_results', None)
    for key in list(session.keys()):
        if key.startswith('q_'):
            session.pop(key)
    return render_template('results.html', 
                           total_score=total_score,
                           full_results=full_results)

# --- অ্যাপ রান করা ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8080)


