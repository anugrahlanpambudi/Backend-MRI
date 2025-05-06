from datetime import datetime, timedelta
from flask import Flask, request, render_template, current_app, Blueprint, jsonify, redirect, url_for, make_response
import hashlib
import jwt


auth_ = Blueprint('auth', __name__)

@auth_.route("/api/login", methods=["POST"])
def sign_in_check():
    email = request.form["email"]
    password = request.form["password"]
    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    SECRET_KEY = current_app.config['SECRET_KEY']
    result = current_app.db.users.find_one(
        {
            "email": email,
            "password": pw_hash,
        }
    )
    if result:
        payload = {
            "id": email,
            "exp": datetime.utcnow() + timedelta(hours=8)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        return jsonify(
            {
                "result": "Success",
                "token": token,
                "msg": "Login Success",
            }
        )
    else:
        return jsonify(
            {
                "result": "Fail",
                "msg": "Wrong email or password!",
            }
        )

@auth_.route("/api/register", methods=["POST"])
def sign_up_save():
    try:
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        exists = current_app.db.users.find_one({"email": email})
        
        if exists:
            return jsonify({
                "result": "Fail",
                "msg": "Email has been used!",
            }), 400
        
        doc = {
            "username": username,
            "email": email,
            "password": password_hash,
            "profile": "",
            "profilePict": "src/images/profiles/profile.jpeg"
        }
        current_app.db.users.insert_one(doc)
        
        return jsonify({
            "result": "Success",
            "msg": "Register Successfully",
        }), 201

    except Exception as e:
        return jsonify({
            "result": "Error",
            "msg": str(e)
        }), 500


@auth_.route("/logout", methods=["DELETE"])
def logout():
    try:
        response = {"message": "Token successfully deleted"}
        resp = make_response(jsonify(response))
        resp.set_cookie("mytoken", "", expires=0, path="/")
        return resp
    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        response = {"message": "Invalid token"}
        return jsonify(response), 401