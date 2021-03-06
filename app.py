import os
from flask import Flask, render_template, redirect, request, url_for, \
    flash, session
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from os import path
if path.exists("env.py"):
    import env

app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get('MONGO_DBNAME')
app.config["MONGO_URI"] = os.environ.get('MONGO_URI')
app.secret_key = os.environ.get('SECRET_KEY')

mongo = PyMongo(app)


# 404 error handling
@app.errorhandler(404)
def page_not_found(e):
    """Handles a 404 and returns the 404 template"""
    return render_template('404.html'), 404


@app.route('/')
def index():
    """Renders homepage template and passes in categories and recipes"""
    categories = mongo.db.categories.find().sort("category_name", 1)
    recipes = list(mongo.db.recipes.find().limit(3).sort("date", -1))
    return render_template(
        "index.html", categories=categories, recipes=recipes)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Registers a user, checks if user exists already"""
    if request.method == "POST":
        existing_user = mongo.db.users.find_one(
            {"user_name": request.form.get("user_name").lower()})

        if existing_user:
            flash("Username already exists. Please try another.", "error")
            return redirect(url_for("register"))

        register = {
            "user_name": request.form.get("user_name").lower(),
            "password": generate_password_hash(request.form.get("password"))
        }
        mongo.db.users.insert_one(register)

        # put new user into session cookie
        session["user"] = request.form.get("user_name").lower()
        flash("Registration successful. You are signed in.")
        return redirect(url_for("profile", user_name=session["user"]))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Logs user in with correct password if they exist"""
    if request.method == "POST":
        existing_user = mongo.db.users.find_one(
            {"user_name": request.form.get("user_name").lower()})

        if existing_user:
            # check hashed password
            if check_password_hash(
                    existing_user["password"],
                    request.form.get("password")):
                session["user"] = request.form.get("user_name").lower()
                flash("Welcome, {}".format(request.form.get("user_name")))
                return redirect(url_for(
                    "profile", user_name=session["user"]))
            else:
                # wrong password
                flash("Incorrect Username/Password combination!", "error")
                return redirect(url_for('login'))

        else:
            # wrong username
            flash("Incorrect Username/Password combination!", "error")
            return redirect(url_for('login'))

    return render_template("login.html")


@app.route("/profile/<user_name>", methods=["GET", "POST"])
def profile(user_name):
    """Renders profile page when logged in"""
    username = mongo.db.users.find_one(
        {"user_name": session["user"]})["user_name"]

    if session["user"]:
        your_recipes = list(mongo.db.recipes.find({"user_name": username}))
        return render_template(
            "profile.html", user_name=username, recipes=your_recipes)

    return redirect(url_for("login"))


@app.route("/pass_change", methods=["GET", "POST"])
def pass_change():
    """Changes the users password"""
    if "user" in session:
        userid = mongo.db.users.find_one(
            {"user_name": session["user"]})["_id"]
        username = mongo.db.users.find_one(
            {"user_name": session["user"]})["user_name"]

        if session["user"] == username:
            if request.method == "POST":
                change_pass = {
                    "user_name": username,
                    "password": generate_password_hash(
                        request.form.get("password"))
                }
                mongo.db.users.update(
                    {"_id": ObjectId(userid)}, change_pass)
                flash("Your password has been changed.")
                return redirect(url_for("profile", user_name=session["user"]))

            return render_template(
                "change_password.html", user_name=session["user"])

        flash(
            "That is not your username and cannot edit them.",
            "error")
        return redirect(url_for("profile", user_name=user_name))

    flash("You are not logged in. Do you wish to log in?")
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    """Logs user out of session"""
    if "user" in session:
        # remove user from session cookie
        flash("You have been logged out.")
        session.pop("user")
        return redirect(url_for("login"))

    flash("Do you wish to log in?")
    return redirect(url_for("login"))


@app.route('/all_recipes')
def all_recipes():
    """Displays All Recipes"""
    categories = mongo.db.categories.find().sort("category_name", 1)
    recipes = list(mongo.db.recipes.find().sort("date", -1))
    return render_template(
        "all-recipes.html", categories=categories, recipes=recipes)


@app.route('/search', methods=["GET", "POST"])
def search():
    """Searches for text from search form"""
    query = request.args.get("query")
    recipes = list(mongo.db.recipes.find({"$text": {"$search": query}}))
    return render_template(
        "search-results.html", recipes=recipes, query=query)


@app.route('/course/<course_name>')
def course_list(course_name):
    """Displays recipes by Course"""
    recipes = list(mongo.db.recipes.find({"course_name": course_name}))
    return render_template(
        "search-results.html", recipes=recipes, course_name=course_name)


@app.route('/category')
def category_list():
    """Returns recipes by category from form select option"""
    category = request.args.get("category_name")
    recipes = list(mongo.db.recipes.find({"category_name": category}))
    return render_template(
        "search-results.html", recipes=recipes,
        category=category)


@app.route('/category/<category_name>')
def category_list_url(category_name):
    """Returns recipes by category from a link or url"""
    recipes = list(mongo.db.recipes.find({"category_name": category_name}))
    return render_template(
        "search-results.html", recipes=recipes,
        category=category_name)


@app.route('/single_recipe/<recipe_id>')
def single_recipe(recipe_id):
    """Returns the selected single recipe"""
    the_recipe = mongo.db.recipes.find_one({"_id": ObjectId(recipe_id)})
    return render_template("single-recipe.html", recipe=the_recipe)


@app.route('/add_recipe', methods=["GET", "POST"])
def add_recipe():
    """Checks if user is logged in, and allows user to add new recipe"""
    if "user" in session:
        if request.method == "POST":
            overall_time = int(request.form.get("prep_time"))
            + int(request.form.get("cook_time"))
            recipe = {
                "title": request.form.get("title"),
                "category_name": request.form.get("category_name"),
                "course_name": request.form.get("course_name"),
                "image_url": request.form.get("image_url"),
                "short_description": request.form.get("short_description"),
                "ingredients": request.form.get("ingredients"),
                "method": request.form.get("method"),
                "portions": request.form.get("portions"),
                "prep_time": request.form.get("prep_time"),
                "cook_time": request.form.get("cook_time"),
                "chef_notes": request.form.get("chef_notes"),
                "total_time": overall_time,
                "nutrition": request.form.get("nutrition"),
                "date": datetime.utcnow(),
                "user_name": session["user"]
            }
            mongo.db.recipes.insert_one(recipe)
            flash("Recipe successfully added.")
            return redirect(url_for("all_recipes"))

        categories = mongo.db.categories.find().sort("category_name", 1)
        courses = mongo.db.courses.find().sort("course_name", 1)
        return render_template(
            "add_recipe.html", categories=categories, courses=courses)

    flash("You must be logged in to add a recipe. Do you wish to log in?")
    return redirect(url_for("login"))


@app.route('/edit_recipe/<recipe_id>', methods=["GET", "POST"])
def edit_recipe(recipe_id):
    """Checks if user is author of recipe, and allows user edit this recipe"""
    if "user" in session:
        the_recipe = mongo.db.recipes.find_one({"_id": ObjectId(recipe_id)})
        recipe_user = the_recipe["user_name"]

        if session["user"] == recipe_user:
            if request.method == "POST":
                overall_time = int(request.form.get("prep_time"))
                + int(request.form.get("cook_time"))
                submit_edit = {
                    "title": request.form.get("title"),
                    "category_name": request.form.get("category_name"),
                    "course_name": request.form.get("course_name"),
                    "image_url": request.form.get("image_url"),
                    "short_description": request.form.get("short_description"),
                    "ingredients": request.form.get("ingredients"),
                    "method": request.form.get("method"),
                    "portions": int(request.form.get("portions")),
                    "prep_time": int(request.form.get("prep_time")),
                    "cook_time": int(request.form.get("cook_time")),
                    "chef_notes": request.form.get("chef_notes"),
                    "total_time": overall_time,
                    "nutrition": request.form.get("nutrition"),
                    "date": datetime.utcnow(),
                    "user_name": session["user"]
                }
                mongo.db.recipes.update(
                    {"_id": ObjectId(recipe_id)}, submit_edit)
                flash("Recipe successfully updated.")
                return redirect(url_for('single_recipe', recipe_id=recipe_id))

            categories = mongo.db.categories.find().sort("category_name", 1)
            courses = mongo.db.courses.find().sort("course_name", 1)
            return render_template(
                "edit_recipe.html",
                recipe=the_recipe, categories=categories, courses=courses)

        flash(
            "You are not the author of this recipe and cannot edit it.",
            "error")
        return render_template("single-recipe.html", recipe=the_recipe)

    flash("You must be logged in to edit a recipe. Do you wish to log in?")
    return redirect(url_for("login"))


@app.route('/delete_recipe/<recipe_id>')
def delete_recipe(recipe_id):
    """Checks if user is author of recipe and allows user delete this recipe"""
    if "user" in session:
        the_recipe = mongo.db.recipes.find_one({"_id": ObjectId(recipe_id)})
        recipe_user = the_recipe["user_name"]

        if session["user"] == recipe_user:
            mongo.db.recipes.remove({"_id": ObjectId(recipe_id)})
            flash("Recipe successfully deleted.")
            return redirect(url_for('all_recipes'))

        flash(
            "You are not the author of this recipe and cannot delete it.",
            "error")
        return render_template("single-recipe.html", recipe=the_recipe)

    flash("You must be logged in to edit a recipe. Do you wish to log in?")
    return redirect(url_for("login"))


@app.route('/get_categories')
def get_categories():
    """Checks if user is logged in, and allows user to view categories"""
    if "user" in session:
        categories = list(mongo.db.categories.find().sort("category_name", 1))
        return render_template("categories.html", categories=categories)

    flash("You must be logged in to view categories. Do you wish to log in?")
    return redirect(url_for("login"))


@app.route('/add_category', methods=["GET", "POST"])
def add_category():
    """Checks if user is logged in, and allows user to add a category"""
    if "user" in session:
        if request.method == "POST":
            category = {
                "category_name": request.form.get("category_name").lower()
            }
            existing_cat = mongo.db.categories.find_one(category)

            if existing_cat:
                flash("This category already exists! Try another?", "error")
                return redirect(url_for("add_category"))

            mongo.db.categories.insert_one(category)
            flash("New Category Added")
            return redirect(url_for('get_categories'))

        return render_template("add_category.html")

    flash("You must be logged in to add a category. Do you wish to log in?")
    return redirect(url_for("login"))


@app.route('/edit_category/<category_id>', methods=["GET", "POST"])
def edit_category(category_id):
    """Checks if user is logged in, and allows user to edit a category"""
    if "user" in session:
        if request.method == "POST":
            submit_edit = {
                "category_name": request.form.get("category_name").lower()
            }
            mongo.db.categories.update(
                {"_id": ObjectId(category_id)}, submit_edit)
            flash("Category successfully updated")
            return redirect(url_for('get_categories'))

        category = mongo.db.categories.find_one({"_id": ObjectId(category_id)})
        return render_template("edit_category.html", category=category)

    flash("You must be logged in to edit a category. Do you wish to log in?")
    return redirect(url_for("login"))


@app.route('/delete_category/<category_id>')
def delete_category(category_id):
    """Checks if user is logged in, and allows user to edit a category"""
    if "user" in session:
        mongo.db.categories.remove({"_id": ObjectId(category_id)})
        flash("Category successfully deleted")
        return redirect(url_for('get_categories'))

    flash("You must be logged in to delete a category. Do you wish to log in?")
    return redirect(url_for("login"))


@app.route('/subscribe', methods=["GET", "POST"])
def subscribe():
    """Subscribes users email, checks if already subscribed"""
    if request.method == "POST":
        # check if subscriber exists
        existing_sub = mongo.db.subscribers.find_one(
            {"email": request.form.get("email").lower()}
        )

        if existing_sub:
            flash("Email is already subscribed!", "error")
            return redirect(request.referrer)

        subscribe = {
            "email": request.form.get("email").lower()
        }
        mongo.db.subscribers.insert_one(subscribe)
        flash("Subscription successful. Thank you.")
        return redirect(request.referrer)

    return render_template("404.html")


if __name__ == '__main__':
    app.run(
        host=os.environ.get('IP'),
        port=os.environ.get('PORT'),
        debug=False)
