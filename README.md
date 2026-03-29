# Guess Baike

## Question Definition

[Guess Baike (猜百科)](https://xiaoce.fun/baike) is a Chinese langugage based puzzle that requires the user to guess the title of a Baike (Chinese Wikipedia) entry.

This solver tries to optimize the guess procedure with the use of Chinese character distribution. To maximize the similarity of the guessing procedures of the algorithm and the human, assumptions are made on the resources achievable by the algorithm.

Assumptions:
1. The algorithm can access the natural Chinese language character distribution, from 1-gram up to 4-gram.
2. The algorithm can know the general domains covered by the Baike, e.g., techonology, news, history, etc..
3. The algorithm does not have access to any specific list of keywords under each domain.
4. The algorithm does not know the selection rule of the daily keyword by the Guess Baike website.


## Interaction

Interaction with Guess Baike website: This program mocks the request to the website, takes the user input, and update to the website.

Run the following command to start interaction

```bash
python cli.py
```

## Get ngram

Get Chinese ngram

```bash
git clone https://github.com/stressosaurus/raw-data-google-ngram.git
cd raw-data-google-ngram
pip3 install --user -r requirements.txt
```

Collect Chinese n-gram with `corpus/clean.ipynb`.


##  Solving strategies (TODO)

1. Maximized character-probability.
2. Maximize info gain through the info given by the body text.
3. Maximize domain possibility.
4. Separate n-grams from the text.
