import nltk

nltk.data.path.append('./nltk_data/')

def download_nltk_packages():
    nltk.download('punkt', './nltk_data/')
    nltk.download('wordnet', './nltk_data/')
    nltk.download('omw-1.4', './nltk_data/')

if __name__ == "__main__":
    download_nltk_packages()