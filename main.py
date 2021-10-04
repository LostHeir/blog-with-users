import functools
import os

from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, CreateBlogUser, LoginUser, CreateComment
from flask_gravatar import Gravatar
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')  # generated via os.urandom(16)
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('POSTGRESSQL_DATABASE_URL', 'sqlite:///blog.db')  # PostgreSQL DB on Heroku, alternatively use sqllite DB for local development
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# INITIALIZE GRAVATAR
gravatar = Gravatar(app,
                    size=100,
                    rating='X',
                    # default='404',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# CREATE LOGIN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return BlogUser.query.get(int(user_id))


# CONFIGURE TABLES
class BlogUser(UserMixin, db.Model):
    __tablename__ = "blog_users"
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)

    # Create realtion One to Many with BlogPost table
    posts = relationship("BlogPost", back_populates="author")
    # Create relation One to Many with PostComment table
    comments = relationship("PostComment", back_populates="author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # Create relation to BlogUser table
    author = relationship("BlogUser", back_populates="posts")
    # Create foreign key to identify author
    author_id = db.Column(db.Integer, db.ForeignKey("blog_users.id"))
    # Create realtion One to Many with PostComment table
    comments = relationship("PostComment", back_populates="post")


class PostComment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    # Create relation to BlogUser table
    author = relationship("BlogUser", back_populates="comments")
    # Create foreign key to identify post author
    author_id = db.Column(db.Integer, db.ForeignKey("blog_users.id"))
    # Create relation to BlogPost table
    post = relationship("BlogPost", back_populates="comments")
    # Create foreign key to identify post
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))

# db.create_all()  # Using for creating tables just once.


# DECORATORS
def admin_required(func):
    @functools.wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_anonymous or current_user.id != 1:
            return abort(403)
        else:
            return func(*args, **kwargs)
    return decorated_function


# ROUTS
@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = CreateBlogUser()
    if form.validate_on_submit():
        try:
            password = form.password.data
            hash_password = generate_password_hash(password=password, method="pbkdf2:sha256", salt_length=8)
            new_user = BlogUser(
                name=form.name.data,
                email=form.email.data,
                password=hash_password
            )
            db.session.add(new_user)
            db.session.commit()
            selected_user = BlogUser.query.filter_by(email=form.email.data).first()
            login_user(selected_user)
            return redirect(url_for("get_all_posts"))
        except IntegrityError:
            flash("Given email already exists, please log in!")
            return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginUser()
    if form.validate_on_submit():
        given_email = form.email.data
        given_password = form.password.data
        try:
            selected_user = BlogUser.query.filter_by(email=given_email).first()
            if check_password_hash(pwhash=selected_user.password, password=given_password):
                login_user(selected_user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Invalid password.")
                return redirect(url_for("login"))
        except AttributeError:
            flash("Given email is not in the user data base.")
            return redirect(url_for("login"))
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CreateComment()
    if form.validate_on_submit() and not current_user.is_anonymous:
        new_comment = PostComment(text=form.text.data, author=current_user, post=requested_post)
        db.session.add(new_comment)
        db.session.commit()
        render_template("post.html", post=requested_post, form=form)
    elif form.validate_on_submit():
        flash("You need to be logged in, to comment posts!")
        return redirect(url_for("login"))
    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
@admin_required
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_required
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
