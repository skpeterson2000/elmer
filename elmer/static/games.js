/* The games, in words: what each is, how it goes, and where its progress
   lives. The table shows the chosen one under the tiles; a phone shows
   them all, because the friend who was invited to play baseball may want
   to know what the golf is. One file, so the two never disagree. */
const GAME_NAMES = {tournament: 'Tournament', shootout: 'Shootout', cutthroat: 'CutThroat', golf: 'Golf', baseball: 'CW Baseball'};
const GAME_ABOUT = {
  tournament: {how: 'Rounds of questions to the whole table at once, points for a right answer and more for a quick one, a leaderboard. The classic, and what an empty table plays on its own fifteen seconds after somebody sits down.',
               progress: 'Every answer counts for the player who gave it, on this unit\'s scoreboard and in their own study record.'},
  shootout: {how: 'One player picks the subject; the rest answer the same question. Miss what the picker made and take a letter. E-L-M-E-R and you are out; the last one standing wins.',
             progress: 'A shootout is a shootout - nothing is kept but the win.'},
  cutthroat: {how: 'Musical chairs with questions: miss and you are out, every right answer keeps its seat. Two left get fifteen questions; level after that, sudden death.',
              progress: 'Nothing saved between games; the answers still count for the players\' study.'},
  golf: {how: 'The slow game. A real course, a question a stroke, one player at a time, no clock. Set up the shot - club, shape, spin - then choose your answer and swing at the meter. Right, and the ball does what you set up, as far as your swing sent it; wrong, and it does it too much - the fade becomes a slice. A tee time lets friends join before the group departs.',
         progress: 'The record board in the pro shop keeps every regular\'s rounds, best to par and aces on this unit.'},
  baseball: {how: 'The machine pitches Morse. Batting is copying: type what you heard and swing - clean is a hit, sized by the pitch. Fielding is sending: key the ball back, clean and in time, for the out. Innings, runs, and the late innings come faster; the last inning pitches a contact.',
             progress: 'The pitching starts at the operator\'s CW rating from the CW page, which the ladder there keeps.'},
};
