# Evaluation of the search

- Run: 2026-11-23 08:18 UTC
- Questions: `data/benchmark/questions.json`, 50, asked on 2026-10-19
- Events: `data/benchmark/events.jsonl`, 1850, index `events-benchmark`
- Index: mistral-embed, chunks of 1000 characters, 150 of overlap
- Reranker: BAAI/bge-reranker-v2-m3 on the first 20 events

## How to read it

For a question, $R$ is the set of its relevant events and $T_k$ the first $k$ events found. Each table gives the mean over the questions with relevant events.

| Metric | For a question | What it says |
|:---:|:---:|---|
| Hit@5 | $\mathbb{1}\left[R \cap T_{5} \neq \emptyset\right]$ | 1 when a relevant event is among the first 5, 0 otherwise. |
| Recall@5 | $\dfrac{\lvert R \cap T_{5} \rvert}{\min(5, \lvert R \rvert)}$ | The relevant events among the first 5, out of the most there can be: 5 relevant events first is a perfect answer, even to a question with 200 of them. |
| Precision@5 | $\dfrac{\lvert R \cap T_{5} \rvert}{5}$ | The share of the first 5 that is relevant: below 1 for a question with fewer than 5 relevant events, 0.20 at most with one. |
| MRR | $\dfrac{1}{r}$ | $r$ is the rank of the first relevant event: 1 when it comes first, 0.5 when second, 0 without any. Its mean is the Mean Reciprocal Rank. |
| Recall@20 | $\dfrac{\lvert R \cap T_{20} \rvert}{\min(20, \lvert R \rvert)}$ | The same recall among the first 20, the candidates of the reranker: it can only bring up an event among them, so it is the same with or without it. |

In bold, the best score of each row. A row where every configuration scores the same has none: no configuration does better there.

## Configurations (45 questions with relevant events)

| Configuration | Hit@5 | Recall@5 | Precision@5 | MRR | Recall@20 |
|---|---|---|---|---|---|
| lexical | 0.93 | 0.81 | 0.64 | 0.92 | 0.79 |
| vector | **1.00** | 0.83 | 0.64 | 0.90 | 0.85 |
| hybrid | 0.96 | 0.84 | 0.65 | 0.92 | **0.89** |
| lexical + rerank | 0.93 | 0.86 | 0.67 | 0.90 | 0.79 |
| vector + rerank | 0.96 | 0.85 | 0.66 | **0.93** | 0.85 |
| hybrid + rerank | 0.96 | **0.89** | **0.69** | **0.93** | **0.89** |

## Question by question

The questions where the configuration of the row has a better Recall@5 than that of the column:

| Better than → | lexical | vector | hybrid | lexical + rerank | vector + rerank | hybrid + rerank |
|---|---|---|---|---|---|---|
| lexical | - | 11 | 5 | 1 | 4 | 1 |
| vector | 8 | - | 7 | 6 | 4 | 4 |
| hybrid | 7 | 9 | - | 2 | 3 | 2 |
| lexical + rerank | 7 | 12 | 7 | - | 3 | 1 |
| vector + rerank | 7 | 10 | 6 | 3 | - | 1 |
| hybrid + rerank | 9 | 13 | 8 | 4 | 4 | - |

## By category: Recall@5

| Category | lexical | vector | hybrid | lexical + rerank | vector + rerank | hybrid + rerank |
|---|---|---|---|---|---|---|
| theme (11) | 0.64 | 0.72 | 0.74 | 0.76 | 0.65 | **0.78** |
| audience (7) | 0.76 | 0.77 | 0.75 | 0.83 | 0.83 | **0.88** |
| practical (6) | 0.81 | 0.83 | 0.80 | **0.87** | **0.87** | **0.87** |
| place (6) | **1.00** | 0.97 | **1.00** | **1.00** | **1.00** | **1.00** |
| time (7) | 0.74 | **0.88** | 0.85 | 0.74 | **0.88** | 0.85 |
| entity (8) | **1.00** | 0.90 | 0.97 | **1.00** | 0.97 | **1.00** |

## By category: MRR

| Category | lexical | vector | hybrid | lexical + rerank | vector + rerank | hybrid + rerank |
|---|---|---|---|---|---|---|
| theme (11) | 0.77 | **0.84** | **0.84** | 0.82 | 0.83 | 0.83 |
| audience (7) | **1.00** | 0.89 | **1.00** | **1.00** | **1.00** | **1.00** |
| practical (6) | **1.00** | 0.88 | 0.85 | **1.00** | **1.00** | **1.00** |
| place (6) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| time (7) | **0.86** | **0.86** | 0.83 | 0.67 | 0.81 | 0.80 |
| entity (8) | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## Each question: Recall@5

Filters: those the analysis found in the question, besides the events from 2026-10-19 on that every search keeps.

| Question | Category | Relevant | Filters | lexical | vector | hybrid | lexical + rerank | vector + rerank | hybrid + rerank |
|---|---|---|---|---|---|---|---|---|---|
| Je cherche une soirée techno à Toulouse | theme | 24 | - | **1.00** | 0.80 | **1.00** | **1.00** | **1.00** | **1.00** |
| Quels films d'animation sont projetés ? | theme | 10 | - | 0.40 | **1.00** | 0.60 | 0.80 | **1.00** | **1.00** |
| Une conférence sur la science-fiction | theme | 3 | - | 0.67 | 0.67 | 0.67 | **1.00** | **1.00** | **1.00** |
| Un spectacle de marionnettes | theme | 1 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Un atelier de dessin ou de peinture pour adultes | theme | 2 | - | 0.00 | **1.00** | 0.50 | 0.00 | 0.00 | 0.00 |
| Un concert de jazz | theme | 3 | - | **1.00** | 0.33 | **1.00** | **1.00** | 0.33 | **1.00** |
| Un concert de rap | theme | 20 | - | 0.80 | 0.20 | 0.80 | **1.00** | 0.20 | **1.00** |
| Une pièce de théâtre | theme | 7 | - | **0.80** | 0.60 | **0.80** | **0.80** | **0.80** | **0.80** |
| Un film documentaire au cinéma | theme | 22 | - | 0.60 | **1.00** | **1.00** | **1.00** | **1.00** | **1.00** |
| Un club manga ou BD | theme | 6 | - | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 |
| De la musique baroque | theme | 2 | - | 0.00 | **0.50** | 0.00 | 0.00 | 0.00 | 0.00 |
| Une activité pour un enfant de 6 ans | audience | 53 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Une sortie avec un bébé de moins de 3 ans | audience | 25 | - | **1.00** | 0.80 | **1.00** | **1.00** | **1.00** | **1.00** |
| Une activité pour les ados | audience | 3 | - | 0.33 | 0.33 | 0.33 | 0.33 | 0.33 | 0.33 |
| Des événements pour les étudiants | audience | 2 | - | 0.50 | **1.00** | **1.00** | **1.00** | **1.00** | **1.00** |
| Une activité accessible en langue des signes | audience | 3 | - | 0.67 | 0.67 | 0.33 | 0.67 | 0.67 | **1.00** |
| Une activité pour les seniors | audience | 1 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Une sortie en famille dimanche | audience | 11 | dates: 2026-10-25 to 2026-10-25 | **0.80** | 0.60 | 0.60 | **0.80** | **0.80** | **0.80** |
| Un concert gratuit | practical | 33 | free | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| J'ai besoin d'aide pour utiliser mon ordinateur | practical | 15 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Quelqu'un pour m'aider à rédiger un courrier administratif | practical | 1 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Une activité gratuite pour enfants ce week-end | practical | 3 | dates: 2026-10-24 to 2026-10-25, free | 0.67 | **1.00** | **1.00** | **1.00** | **1.00** | **1.00** |
| Une activité sans réservation | practical | 68 | - | **0.40** | 0.20 | 0.00 | **0.40** | **0.40** | **0.40** |
| Où jouer aux jeux vidéo gratuitement ? | practical | 5 | free | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 | 0.80 |
| Que faire au couvent des Jacobins ? | place | 4 | venue: Jacobins | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Quels événements à la chapelle des Carmélites ? | place | 13 | venue: Carmélites | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Que faire dans le quartier Saint-Cyprien ? | place | 17 | district: Saint-Cyprien | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Quels films passent au Cratère ? | place | 37 | venue: Cratère | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Que faire au Quai des Savoirs ? | place | 30 | venue: Quai des Savoirs | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Quels concerts au Zénith ? | place | 8 | - | **1.00** | 0.80 | **1.00** | **1.00** | **1.00** | **1.00** |
| Que faire ce week-end ? | time | 59 | dates: 2026-10-24 to 2026-10-25 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Des événements pour Halloween ? | time | 27 | dates: 2026-10-31 to 2026-10-31 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Quelles sorties en décembre ? | time | 191 | dates: 2026-12-01 to 2026-12-31 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Que faire ce soir ? | time | 4 | dates: 2026-10-19 to 2026-10-19 | 0.00 | **0.75** | **0.75** | 0.00 | **0.75** | **0.75** |
| Des animations pour Noël ? | time | 14 | dates: 2026-12-01 to 2026-12-25 | **1.00** | 0.60 | **1.00** | **1.00** | **1.00** | **1.00** |
| Que faire pendant les vacances de la Toussaint ? | time | 223 | dates: 2026-10-19 to 2026-11-07 | 0.40 | **1.00** | 0.60 | 0.60 | 0.80 | 0.80 |
| Qu'est-ce qu'il y avait aux Journées du patrimoine ? | time | 209 | dates: 2026-09-15 to 2026-09-22 | **0.80** | **0.80** | 0.60 | 0.60 | 0.60 | 0.40 |
| Quand a lieu Harpissima ? | entity | 2 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Où voir les œuvres de Nicolas Dhervillers ? | entity | 4 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Y a-t-il des films de Jonás Trueba ? | entity | 3 | - | **1.00** | 0.67 | **1.00** | **1.00** | **1.00** | **1.00** |
| Où voir le film Mémoire de fille ? | entity | 2 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Des films avec Valérie Dréville ? | entity | 4 | - | **1.00** | 0.50 | 0.75 | **1.00** | 0.75 | **1.00** |
| Qu'y a-t-il au festival Lumières sur le Quai ? | entity | 31 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Quand joue Dub Inc à Toulouse ? | entity | 1 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| L'escape game sur l'intelligence artificielle, c'est quand ? | entity | 1 | - | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## Out-of-scope questions (5): the first event found

| Question | lexical | vector | hybrid | lexical + rerank | vector + rerank | hybrid + rerank |
|---|---|---|---|---|---|---|
| Un match de rugby du Stade Toulousain | VEN1 à Toulouse | L2B - TOULOUSE | Gaston Roquemaurel, explorateur toulous… | Warhaus | DINAA A TOULOUSE | DINAA A TOULOUSE |
| Que faire à Paris ce soir ? | - | Visite Famille: L'horloge et le magicie… | Visite Famille: L'horloge et le magicie… | - | Visite guidée "Femme, féminité et fémin… | Visite guidée "Femme, féminité et fémin… |
| Un bon restaurant italien | Dimanche Electro #25 invite B-Maïky | Le dernier pour la route / Rencontre av… | Saison musicale - Messe des Gargouilles… | TOULOUSE, VOLVIMOS… PERO NO CON EL EX | DINAA A TOULOUSE | DINAA A TOULOUSE |
| Les horaires de la piscine Nakache | Ce qui nous mène à toi | En avant les histoires ! | Ce qui nous mène à toi | Ce qui nous mène à toi | Le temps des tout-petits | Ce qui nous mène à toi |
| Le prochain match du TFC | JEANJASS à TOULOUSE | Animation jeux vidéo | Club de lecteurs adultes | Dea Matrona | DESTINATION FINALE : Le Cri De La Mouet… | DESTINATION FINALE : Le Cri De La Mouet… |

The first score of the reranker, between 0 and 1. A threshold that turns away every out-of-scope question would also turn away those of the last column:

| Configuration | With relevant events: mean | lowest | Out of scope: mean | highest | With relevant events, at most that highest |
|---|---|---|---|---|---|
| lexical + rerank | 0.610 | 0.001 | 0.001 | 0.002 | 1 / 44 |
| vector + rerank | 0.565 | 0.004 | 0.003 | 0.009 | 2 / 45 |
| hybrid + rerank | 0.600 | 0.004 | 0.003 | 0.009 | 2 / 45 |
