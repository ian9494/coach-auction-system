// Test-only oracle: extract named functions from server.js, never execute entrypoint.
// No require, network, timer or disk APIs are exposed inside the VM.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const fixture = JSON.parse(fs.readFileSync(path.join(root,'tests/fixtures/auction_cases.json'),'utf8'));
const source = fs.readFileSync(path.join(root,'server.js'),'utf8');
const names = ['getCoachPlayerCount','getCoachSpent','getPlayerZone','getCoachZonePlayerCount','getBidRules','getBidError','pruneInvalidBids','applyAutoMinimumBids','getWinner','resetBids','startAuction','pauseAuction','resumeAuction','endAuction','undoLastAward'];
const functions = names.map(name => {
  const match = source.match(new RegExp('^function '+name+'\\([^]*?^}', 'm'));
  if (!match) throw Error('Cannot extract '+name);
  return match[0];
}).join('\n');
const players = fs.readFileSync(path.join(root,fixture.roster.member_file),'utf8').trim().split(/\r?\n/);
const coaches = fs.readFileSync(path.join(root,fixture.roster.coach_file),'utf8').trim().split(/\r?\n/).map(x=>x.split(',')[0]);
const results = fixture.cases.map(c => {
  const initial = JSON.parse(JSON.stringify(c.initial));
  const context = vm.createContext({state:initial, coachBudgets:initial.budgets, auctionHistory:initial.history,
    lastAwardUndo:initial.lastAwardUndo, auctionTimer:null, COACHES:coaches, MEMBER_NAMES:players,
    TEAM_SIZE:5, RESERVED_BID_PER_REMAINING_SLOT:100, MIN_SPEND_AFTER_SECOND_PLAYER:300, MAX_BID_AMOUNT:500,
    PLAYER_ZONE_CONFIG:[{id:1,size:8,coachLimit:1},{id:2,size:8,coachLimit:1},{id:3,size:24,coachLimit:3}],
    saveState(){},broadcastState(){},saveHistoryToCSV(){},startAuctionTimer(){},
    clearInterval(){throw Error('Timer unexpectedly active');}, args:null, output:null,
    rng_values:[...(c.rng_values || [0])], Date:class {toLocaleString(){return 'TEST_CLOCK';}}});
  vm.runInContext('Math.random = () => { if (!rng_values.length) throw Error("RNG exhausted"); return rng_values.shift(); };\n'+functions,context,{timeout:1000});
  for(const step of c.steps){
    context.args = step.args;
    const commands={
      validate_bid:`const error = getBidError(args.coachId,args.amount); const r=getBidRules(args.coachId); output={valid:error===null,error_category: error===null?null:error.startsWith('請輸入')?'invalid_amount':error.startsWith('出價不得')?'below_minimum':error.includes('超過剩餘預算')?'above_budget':error.startsWith('第 ')?'zone_limit':error.includes('隊伍已滿')?'team_full':error.startsWith('T2 ')?'second_player_minimum':'above_rule_max',...r};`,
      select_winner:`output=getWinner(); output.candidates=Object.entries(state.bids).filter(([id,b])=>b!==null && typeof b==='number' && !getBidError(id,b) && b===output.winningAmount).map(([id])=>id);`,
      submit_bid:`if(state.status!=='running') throw Error('not_running'); if(!COACHES.includes(args.coachId)) throw Error('invalid_coach'); const e=getBidError(args.coachId,args.amount); if(e) throw Error(e); state.bids[args.coachId]=args.amount;`,
      set_minimum_bid:`state.minimumBid=args.amount; pruneInvalidBids();`,
      start_auction:`startAuction(args.playerName,args.duration);`, pause:`pauseAuction();`,resume:`resumeAuction();`,
      undo_last_award:`if(!undoLastAward()) throw Error('nothing_to_undo');`,end_auction:`endAuction();`
    };
    if(!commands[step.operation]) throw Error('Unknown operation '+step.operation);
    vm.runInContext('{'+commands[step.operation]+'}',context,{timeout:1000});
  }
  const result=context.output || Object.fromEntries(['status','currentPlayer','timeLeft','duration','minimumBid','bids','winner','winningAmount'].map(k=>[k,context.state[k]]));
  if(!context.output) Object.assign(result,{budgets:context.coachBudgets,history:context.auctionHistory,canUndo:context.lastAwardUndo!==null});
  return {id:c.id,result:JSON.parse(JSON.stringify(result))};
});
process.stdout.write(JSON.stringify(results)+'\n');
