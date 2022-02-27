# Calculus-Calculator-with-Chatbot
<img src="demo.gif" width="100%" height="100%">

## Getting Started

Setup project environment with [virtualenv](https://virtualenv.pypa.io) and [pip](https://pip.pypa.io).

```bash
virtualenv env
source env/bin/activate
pip install -r requirements.txt

# download nltk data for WordNetLemmatizer and word_tokenize
python chatbot/nltk_packages.py 

python manage.py runserver
```
