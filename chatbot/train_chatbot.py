import random
from keras.optimizers import SGD
from keras.layers import Dense, Activation, Dropout
from keras.models import Sequential
import numpy as np
import pickle
import json
import nltk

from nltk.stem import WordNetLemmatizer

nltk.download('all', download_dir='./nltk_data/')

lemmatizer = WordNetLemmatizer()

words = []
classes = []
documents = []
ignore_words = ['?', '!']
data_file = open('./chatbot/intents.json').read()
intents = json.loads(data_file)

 
for intent in intents['intents']:
    for pattern in intent['patterns']:

        tockenized_word_patterns = nltk.word_tokenize(pattern)
        words.extend(tockenized_word_patterns)
        documents.append((tockenized_word_patterns, intent['tag']))

        if intent['tag'] not in classes:
            classes.append(intent['tag'])

words = [lemmatizer.lemmatize(word.lower())
         for word in words if word not in ignore_words]
words = sorted(list(set(words)))
classes = sorted(list(set(classes)))

pickle.dump(words, open('words.pkl', 'wb'))
pickle.dump(classes, open('classes.pkl', 'wb'))

# begin training
training = []

output_empty = [0] * len(classes)

for document in documents:
    bag = []

    tokenized_words = document[0]
    # lemmatize each word - create base word, in attempt to represent related words
    tokenized_words = [lemmatizer.lemmatize(
        word.lower()) for word in tokenized_words]

    for word in words:
        bag.append(1) if word in tokenized_words else bag.append(0)

    output_row = list(output_empty)
    output_row[classes.index(document[1])] = 1

    training.append([bag, output_row])

random.shuffle(training)
training = np.array(training)

train_x_bags = list(training[:, 0])
train_y_output_rows = list(training[:, 1])
print("Training data created")

# Create model - 3 layers. First layer 128 neurons, second layer 64 neurons and 3rd output layer contains number of neurons
# equal to number of intents to predict output intent with softmax
model = Sequential()
model.add(Dense(128, input_shape=(len(train_x_bags[0]),), activation='relu'))
model.add(Dropout(0.5))
model.add(Dense(64, activation='relu'))
model.add(Dropout(0.5))
model.add(Dense(len(train_y_output_rows[0]), activation='softmax'))

# Compile model. Stochastic gradient descent with Nesterov accelerated gradient.
sgd = SGD(lr=0.01, decay=1e-6, momentum=0.9, nesterov=True)
model.compile(loss='categorical_crossentropy',
              optimizer=sgd, metrics=['accuracy'])

hist = model.fit(np.array(train_x_bags), np.array(
    train_y_output_rows), epochs=300, batch_size=10, verbose=1)
model.save('chatbot_model.h5', hist)

print("model created")
