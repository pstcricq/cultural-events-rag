# Evaluation of the answers

- Run: 2026-11-20 10:47 UTC
- Questions: `data/benchmark/questions.json`, 50, asked on 2026-10-19
- Events: `data/benchmark/events.jsonl`, 1850, index `events-benchmark`
- Index: mistral-embed, chunks of 1000 characters, 150 of overlap
- Search: hybrid + rerank, the first 5 events given to the LLM
- Answers: ministral-14b-latest, in 1473 s
- Judge: ministral-14b-latest (Ragas), in 10712 s
- Calls to the chat models: 2 a minute, the quota of the Mistral plan

## How to read it

For a question, $R$ is the set of its relevant events, $C$ the events found and given to the LLM, $A$ those its answer recommends. The first three metrics are exact; the last three are scored by an LLM judge (Ragas), for the questions with relevant events. Each mean is over the questions a metric applies to, counted beside it.

| Metric | For a question | What it says |
|:---:|:---:|---|
| Recommendation precision | $\dfrac{\lvert A \cap R \rvert}{\lvert A \rvert}$ | The share of the events recommended that are relevant, for a question with at least one recommended. |
| Recommendation recall | $\dfrac{\lvert A \cap R \cap C \rvert}{\lvert R \cap C \rvert}$ | The share of the relevant events given to the LLM that it recommends, for a question with at least one given: what the answer keeps of what the search brought. |
| Abstention | $\mathbb{1}\left[A = \emptyset\right]$ | 1 when an out-of-scope question is answered without any event. |
| Faithfulness | $\dfrac{\text{claims of the answer the events } C \text{ support}}{\text{claims of the answer}}$ | 1 when the answer invents nothing beyond the events given to the LLM. |
| Answer relevancy | $\cos(q, \hat{q})$ | The question $\hat{q}$ the judge writes back from the answer, compared with the question $q$ by the cosine of their embeddings: close to 1 when the answer addresses the question directly. |
| Factual correctness | $\dfrac{2\,P\,R}{P + R}$ | $P$: the share of the claims of the answer the reference answer supports; $R$: the share of the claims of the reference the answer gives. The reference picks a few events when many are relevant: an answer citing others loses points without being wrong. |

## Scores (50 questions)

| Metric | Mean | Questions |
|---|---|---|
| Recommendation precision | 0.92 | 43 |
| Recommendation recall | 0.88 | 43 |
| Abstention (out of scope) | 0.80 | 5 |
| Faithfulness | 0.88 | 45 |
| Answer relevancy | 0.79 | 45 |
| Factual correctness | 0.38 | 45 |

## By category

| Category | Recommendation precision | Recommendation recall | Faithfulness | Answer relevancy | Factual correctness |
|---|---|---|---|---|---|
| theme (11) | 0.81 | 0.81 | 0.87 | 0.68 | 0.35 |
| audience (7) | 1.00 | 0.87 | 0.92 | 0.77 | 0.57 |
| practical (6) | 0.88 | 0.82 | 0.83 | 0.80 | 0.36 |
| place (6) | 1.00 | 0.93 | 0.88 | 0.84 | 0.21 |
| time (7) | 0.88 | 0.91 | 0.83 | 0.83 | 0.18 |
| entity (8) | 1.00 | 0.97 | 0.94 | 0.88 | 0.61 |

## Each question (45 with relevant events)

Relevant given: the relevant events among those given to the LLM. Relevant recommended: the relevant events among those its answer recommends. Every answer is in the JSON file beside this report.

| Question | Category | Relevant given | Relevant recommended | Precision | Recall | Faithfulness | Answer relevancy | Factual correctness |
|---|---|---|---|---|---|---|---|---|
| Je cherche une soirée techno à Toulouse | theme | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 0.92 | 0.83 | 0.36 |
| Quels films d'animation sont projetés ? | theme | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 1.00 | 0.88 | 0.29 |
| Une conférence sur la science-fiction | theme | 3 / 5 | 2 / 2 | 1.00 | 0.67 | 1.00 | 0.85 | 0.62 |
| Un spectacle de marionnettes | theme | 1 / 5 | 1 / 2 | 0.50 | 1.00 | 0.79 | 0.83 | 0.40 |
| Un atelier de dessin ou de peinture pour adultes | theme | 0 / 5 | 0 / 0 | - | - | 0.80 | 0.00 | 0.14 |
| Un concert de jazz | theme | 3 / 5 | 3 / 3 | 1.00 | 1.00 | 0.89 | 0.85 | 0.84 |
| Un concert de rap | theme | 5 / 5 | 3 / 3 | 1.00 | 0.60 | 1.00 | 0.81 | 0.21 |
| Une pièce de théâtre | theme | 4 / 5 | 4 / 4 | 1.00 | 1.00 | 0.93 | 0.82 | 0.31 |
| Un film documentaire au cinéma | theme | 5 / 5 | 0 / 0 | - | 0.00 | 0.67 | 0.00 | 0.27 |
| Un club manga ou BD | theme | 4 / 5 | 4 / 5 | 0.80 | 1.00 | 0.91 | 0.83 | 0.37 |
| De la musique baroque | theme | 0 / 5 | 0 / 2 | 0.00 | - | 0.67 | 0.84 | 0.00 |
| Une activité pour un enfant de 6 ans | audience | 5 / 5 | 3 / 3 | 1.00 | 0.60 | 0.91 | 0.83 | 0.00 |
| Une sortie avec un bébé de moins de 3 ans | audience | 5 / 5 | 4 / 4 | 1.00 | 0.80 | 0.80 | 0.81 | 0.59 |
| Une activité pour les ados | audience | 1 / 5 | 1 / 1 | 1.00 | 1.00 | 1.00 | 0.72 | 0.86 |
| Des événements pour les étudiants | audience | 2 / 5 | 2 / 2 | 1.00 | 1.00 | 0.88 | 0.72 | 0.77 |
| Une activité accessible en langue des signes | audience | 3 / 5 | 2 / 2 | 1.00 | 0.67 | 0.86 | 0.85 | 0.67 |
| Une activité pour les seniors | audience | 1 / 5 | 1 / 1 | 1.00 | 1.00 | 1.00 | 0.71 | 0.67 |
| Une sortie en famille dimanche | audience | 4 / 5 | 4 / 4 | 1.00 | 1.00 | 1.00 | 0.77 | 0.42 |
| Un concert gratuit | practical | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 0.93 | 0.86 | 0.00 |
| J'ai besoin d'aide pour utiliser mon ordinateur | practical | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 0.82 | 0.76 | 0.36 |
| Quelqu'un pour m'aider à rédiger un courrier administratif | practical | 1 / 5 | 1 / 1 | 1.00 | 1.00 | 0.88 | 0.72 | 0.67 |
| Une activité gratuite pour enfants ce week-end | practical | 3 / 5 | 2 / 2 | 1.00 | 0.67 | 0.92 | 0.80 | 0.64 |
| Une activité sans réservation | practical | 2 / 5 | 1 / 2 | 0.50 | 0.50 | 0.73 | 0.84 | 0.00 |
| Où jouer aux jeux vidéo gratuitement ? | practical | 4 / 5 | 3 / 4 | 0.75 | 0.75 | 0.70 | 0.84 | 0.48 |
| Que faire au couvent des Jacobins ? | place | 4 / 5 | 4 / 4 | 1.00 | 1.00 | 0.94 | 0.85 | 0.30 |
| Quels événements à la chapelle des Carmélites ? | place | 5 / 5 | 4 / 4 | 1.00 | 0.80 | 0.81 | 0.89 | 0.24 |
| Que faire dans le quartier Saint-Cyprien ? | place | 5 / 5 | 4 / 4 | 1.00 | 0.80 | 0.84 | 0.77 | 0.24 |
| Quels films passent au Cratère ? | place | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 0.83 | 0.84 | 0.21 |
| Que faire au Quai des Savoirs ? | place | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 0.92 | 0.82 | 0.15 |
| Quels concerts au Zénith ? | place | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 0.94 | 0.84 | 0.10 |
| Que faire ce week-end ? | time | 5 / 5 | 4 / 4 | 1.00 | 0.80 | 0.85 | 0.84 | 0.17 |
| Des événements pour Halloween ? | time | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 1.00 | 0.87 | 0.13 |
| Quelles sorties en décembre ? | time | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 1.00 | 0.77 | 0.00 |
| Que faire ce soir ? | time | 3 / 5 | 3 / 3 | 1.00 | 1.00 | 0.44 | 0.80 | 0.44 |
| Des animations pour Noël ? | time | 5 / 5 | 4 / 4 | 1.00 | 0.80 | 0.73 | 0.78 | 0.29 |
| Que faire pendant les vacances de la Toussaint ? | time | 4 / 5 | 3 / 4 | 0.75 | 0.75 | 0.94 | 0.88 | 0.00 |
| Qu'est-ce qu'il y avait aux Journées du patrimoine ? | time | 2 / 5 | 2 / 5 | 0.40 | 1.00 | 0.87 | 0.85 | 0.22 |
| Quand a lieu Harpissima ? | entity | 2 / 5 | 2 / 2 | 1.00 | 1.00 | 1.00 | 0.80 | 0.57 |
| Où voir les œuvres de Nicolas Dhervillers ? | entity | 4 / 5 | 4 / 4 | 1.00 | 1.00 | 0.93 | 0.93 | 0.59 |
| Y a-t-il des films de Jonás Trueba ? | entity | 3 / 5 | 3 / 3 | 1.00 | 1.00 | 1.00 | 0.79 | 0.67 |
| Où voir le film Mémoire de fille ? | entity | 2 / 5 | 2 / 2 | 1.00 | 1.00 | 0.78 | 0.92 | 0.62 |
| Des films avec Valérie Dréville ? | entity | 4 / 5 | 3 / 3 | 1.00 | 0.75 | 0.88 | 0.86 | 0.48 |
| Qu'y a-t-il au festival Lumières sur le Quai ? | entity | 5 / 5 | 5 / 5 | 1.00 | 1.00 | 0.95 | 0.90 | 0.33 |
| Quand joue Dub Inc à Toulouse ? | entity | 1 / 5 | 1 / 1 | 1.00 | 1.00 | 1.00 | 0.92 | 0.89 |
| L'escape game sur l'intelligence artificielle, c'est quand ? | entity | 1 / 5 | 1 / 1 | 1.00 | 1.00 | 1.00 | 0.91 | 0.73 |

## Out-of-scope questions (5)

| Question | Recommended | Answer |
|---|---|---|
| Un match de rugby du Stade Toulousain | 0 | Malheureusement, aucun événement correspondant à un match de rugby du Stade Toulousain n'est disponible dans les donnée… |
| Que faire à Paris ce soir ? | 0 | Je suis désolé, je ne peux recommander que des événements à Toulouse. Si vous souhaitez des suggestions pour ce soir à … |
| Un bon restaurant italien | 2 | Voici deux événements qui pourraient vous plaire pour une ambiance italienne à Toulouse : - Saison musicale - Messe des… |
| Les horaires de la piscine Nakache | 0 | Je n'ai trouvé aucun événement lié à la piscine Nakache dans les informations fournies. Pourriez-vous préciser votre de… |
| Le prochain match du TFC | 0 | Malheureusement, aucun événement lié au Toulouse Football Club (TFC) n'est prévu dans les données fournies pour le mome… |
