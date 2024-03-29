# -*- coding: utf-8 -*-
"""Spanish_Transducer.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/13fsvK8WgIxrC-hjyFto3FdTsP-MtevZ4

# Spanish Transducer

This files builds up a finite state trabsducer which transduces the infinitive form of Spanish verbs to the preterite (past tense) form in the 3rd person singular.
"""

import os
import pandas as pd
from tabulate import tabulate
pdtabulate=lambda df:tabulate(df,headers='keys',tablefmt='psql', showindex=False)

def readVerbFile(file):
    url='https://drive.google.com/u/0/uc?id=1U6vrmAKep0hDscPrCZ7yJKjFQmPQsfG2&export=download'
    df = pd.read_csv(url, header=None)

    return df.values.tolist()

verbs = readVerbFile('verbsList.csv')

def testFST(print_examples = 'all'):
    assert print_examples in {'all', 'incorrect', 'none'}, "print_examples must be 'all', 'incorrect', or 'none'"
    rule_classes = [('0a*', "0a* Regular -Car verb (stem end in consonant)", 'hablar      ==>  habló'), ('0b*', "0b* Regular -Var verb (stem end in vowel)", 'pasear      ==>  paseó'), ('0c*', "0c* Regular -er verb", 'comer       ==>  comió'), ('0d*', "0d* Regular -ir verb (excluding -guir, -quir)", 'abrir       ==>  abrió'), ('1a', "1a  Verbs in -ñer", 'tañer       ==>  tañó'), ('1b', "1b  Verbs in -ñir (excluding -eñir)", 'gañir       ==>  gañó'), ('2a', "2a  Verbs in -Ver", 'leer        ==>  leyó'), ('2b', "2b  Verbs in -Vir", 'construir   ==>  construyó'), ('2c*', "2c* Verbs in -guir (excluding -eguir)", 'distinguir  ==>  distinguió'), ('2d*', "2d* Verbs in -quir", 'delinquir   ==>  delinquió'), ('3a', "3a  Verbs in -eCir", 'pedir       ==>  pidió'), ('3b', "3b  Verbs in -eCCir", 'sentir      ==>  sintió'), ('3c', "3c  Verbs in -eCCCir", 'henchir     ==>  hinchió'), ('3d', "3d  Verbs in -eguir", 'seguir      ==>  siguió'), ('3e', "3e  Verbs in -eñir", 'heñir       ==>  hiñó')]

    f = buildFST()
    myParses = f.parseInputList([x[0] for x in verbs])
    scores, totals, examples = {}, {}, []

    for i in range(len(verbs)):
        lemma, form, clas = verbs[i]
        output = myParses[i]
        scores[clas] = scores.get(clas, 0)
        totals[clas] = totals.get(clas, 0) + 1
        if print_examples == 'all' or print_examples == 'incorrect' and form != output:
            examples += [(lemma, form, output, 'CORRECT' if form == output else 'INCORRECT')]
        if form == output: scores[clas] += 1

    if print_examples != 'none' and len(examples) > 0:
        examples = pd.DataFrame.from_records(examples, columns = ['Input', 'Correct Output', 'Returned Output', 'Result'])
        print(pdtabulate(examples))

    data= []

    # We use a scoring method that accounts for (1) the fact that the default FST gets many verbs correct
    #                                           (2) the class inbalance among the different rules
    # p_scores is for verbs that the default FST gets correct, q_scores for verbs it gets wrong
    # Each contains a list of accuracies for each category group (for example, all of the examples where rule 2 applies are in one group)
    p_scores, q_scores = {'0*': [], '2*': []}, {'1': [], '2': [], '3': []}
    for clas, msg, ex in rule_classes:
        acc = scores[clas]/totals[clas]
        data += [(msg, ex, scores[clas], totals[clas], 100*acc)]
        if '0' in clas: p_scores['0*'].append(acc)
        elif '1' in clas: q_scores['1'].append(acc)
        elif '2' in clas and '*' not in clas: q_scores['2'].append(acc)
        elif '2' in clas and '*' in clas: p_scores['2*'].append(acc)
        elif '3' in clas:
            if clas in {'3a', '3b', '3c'}: q_scores['3'] += [acc, acc, acc] # Weight these higher than -eguir and -eñir
            else: q_scores['3'].append(acc)
        else: assert False, 'should not get here ' + clas

    p_scores = [sum(v) / len(v) for k, v in p_scores.items()] # Get the average for each category group
    q_scores = [sum(v) / len(v) for k, v in q_scores.items()]

    p_scores = [p_scores[0]] * 3 + [p_scores[1]] # Weight 0* higher than 2*

    # Score by averaging the p and q scores, then applying grading formula
    p, q = sum(p_scores) / len(p_scores), sum(q_scores) / len(q_scores)
    final_score = q/2 * (1+p) # Score will be 0 when p is 100% and q is 0%; score will be 100% when p and q are both 100%

    print('\nScorecard:')
    data = pd.DataFrame.from_records(data, columns = ['Category', 'Example', 'Correct', 'Total', 'Accuracy (%)'])
    print(pdtabulate(data))

    print("Overall Score:", str(final_score*100) + '%')

class Transition:
    # string_in
    # string_out
    def __init__(self, inState, inString, outString, outState):
        self.state_in = inState
        self.string_in = inString
        self.string_out = outString
        self.state_out = outState

    def equals(self, t):
        if self.state_in == t.state_in \
        and self.string_in == t.string_in \
        and self.string_out == t.string_out \
        and self.state_out == t.state_out:
            return True
        else:
            return False

class FSTstate:
    # id: an integer ID of the state
    # isFinal: is this a final state?
    def __init__(self, n, isF, fst):
        self.id = n
        self.isFinal = isF
        self.transitions = dict() # map inStrings to a set of all possible transitions
        self.FST = fst

    def addTransition(self, inString, outString, outState):
        newTransition = Transition(self, inString, outString, outState)
        if inString in self.transitions:
            for t in self.transitions[inString]:
                if t.equals(newTransition):
                    return
            self.transitions[inString].add(newTransition)
        else:
            self.transitions[inString] = set([])
            self.transitions[inString].add(newTransition)

    def parseInputFromStartState(self, inString):
        parseTuple = ("", self.id)
        parses = []
        (accept, stringParses) = self.parseInput(inString)
        if accept:
            for p in stringParses:
                completeParse = [parseTuple]
                completeParse.extend(p)
                parses.append(completeParse)
        return (accept, parses)

    def parseInput(self, inString):
        parses = []
        isAccepted = True

        DEBUG = False
        if DEBUG:
            print("parseInput: state: ", self.id, " parsing: " , inString)

        # Case 1: no suffix
        if inString == "":
            epsilonParses = []
            epsilonAccepted = False
            # try all epsilon transitions
            if "" in self.transitions:
                transSet = self.transitions[""]
                for t in transSet:
                    outString = t.string_out
                    toStateID = t.state_out
                    toState = self.FST.allStates[toStateID]
                    parseTuple = (outString, toStateID)
                    (suffixAccepted, suffixParses) = toState.parseInput(inString)
                    if suffixAccepted:
                        epsilonAccepted = True
                        if suffixParses == []: #accepts.
                            parse_s = [parseTuple]
                            epsilonParses.append(parse_s)
                        else:
                            for s in suffixParses:
                                parse_s = [parseTuple]
                                parse_s.extend(s)
                                epsilonParses.append(parse_s)
            # if epsilon is accepted, add all its parses
            if epsilonAccepted:
                parses.extend(epsilonParses)
            # if this is a final state, add an empty parse
            if self.isFinal or parses != []:
                if DEBUG:
                    print("Accepted in state ", self.id)
                return (True, parses)
            else:
                if DEBUG:
                    print("Rejected in state ", self.id)
                return (False, None)
        # case 2: non-empty suffix: there needs to be one suffix that parses!)
        hasAcceptedSuffix = False;
        for i in range(0,len(inString)+1):
            prefix = inString[0:i]
            suffix = inString[i:len(inString)]
            if DEBUG:
                print("\t prefix: \'", prefix, "\' I=", i)
            if prefix in self.transitions:
                if DEBUG:
                     print("\t prefix: ", prefix,  "suffix: ", suffix, "I=", i)
                transSet = self.transitions[prefix]
                for t in transSet:
                    outString = t.string_out
                    toStateID = t.state_out
                    toState = self.FST.allStates[toStateID]
                    parseTuple = (outString, toStateID)
                    (suffixAccepted, suffixParses) = toState.parseInput(suffix)
                    if suffixAccepted:
                        hasAcceptedSuffix = True
                        if suffixParses == []:
                            parse_s = [parseTuple]
                            parses.append(parse_s)
                            thisPrefixParses = True
                        for s in suffixParses:
                            parse_s = [parseTuple]
                            parse_s.extend(s)
                            parses.append(parse_s)
        if hasAcceptedSuffix:
            return (True, parses)
        else:
            return (False, None)



    def printState(self):
        if self.isFinal:
            FINAL = "FINAL"
        else: FINAL = ""
        print("State", self.id, FINAL)
        for inString in self.transitions:
            transList = self.transitions[inString]
            for t in transList:
                print("\t", inString, ":", t.string_out, " => ", t.state_out)




class FST:
    def __init__(self, initialStateName="q0"):
        self.nStates = 0
        self.initState = FSTstate(initialStateName, False, self)
        self.allStates = dict()
        self.allStates[initialStateName] = self.initState

    def addState(self, name, isFinal=False):
        if name in self.allStates:
            print("ERROR addState: state", name, "exists already")
            sys.exit()
        elif len(self.allStates) >= 30:
            print("ERROR addState: you can't have more than 30 states")
            sys.exit()
        else:
            newState = FSTstate(name, isFinal, self)
            self.allStates[name] = newState

    def addTransition(self, inStateName, inString, outString, outStateName):
        if (len(inString) > 1):
            print("ERROR: addTransition: input string ", inString, " is longer than one character")
            sys.exit()
        if inStateName not in self.allStates:
            print("ERROR: addTransition: state ", inStateName, " does not exist")
            sys.exit()
        if outStateName not in self.allStates:
            print("ERROR: addTransition: state ", outStateName, " does not exist")
            sys.exit()
        inState = self.allStates[inStateName]
        inState.addTransition(inString, outString, outStateName)

    # epsilon:epsilon
    def addEpsilonTransition(self, inStateName, outStateName):
        if inStateName not in self.allStates:
            print("ERROR: addEpsilonTransition: state ", inStateName, " does not exist")
            sys.exit()
        if outStateName not in self.allStates:
            print("ERROR: addEpsilonTransition: state ", outStateName, " does not exist")
            sys.exit()
        if inStateName == outStateName:
            print("ERROR: we don't allow epsilon loops")
            sys.exit()
        inState = self.allStates[inStateName]
        inState.addTransition("", "", outStateName)

    # map every element in inStringSet to itself
    def addSetTransition(self, inStateName, inStringSet, outStateName):
         if inStateName not in self.allStates:
            print("ERROR: addSetTransition: state ", inStateName, " does not exist")
            sys.exit()
         if outStateName not in self.allStates:
            print("ERROR: addSetTransition: state ", outStateName, " does not exist")
            sys.exit()
         for s in inStringSet:
            self.addTransition(inStateName, s, s, outStateName)

    # map string to itself
    def addSelfTransition(self, inStateName, inString, outStateName):
         if inStateName not in self.allStates:
            print("ERROR: addSetTransition: state ", inStateName, " does not exist")
            sys.exit()
         if outStateName not in self.allStates:
            print("ERROR: addSetTransition: state ", outStateName, " does not exist")
            sys.exit()
         self.addTransition(inStateName, inString, inString, outStateName)

    # map every element in inStringSet to outString
    def addSetToStringTransition(self, inStateName, inStringSet, outString, outStateName):
         if inStateName not in self.allStates:
            print("ERROR: addSetDummyTransition: state ", inStateName, " does not exist")
            sys.exit()
         if outStateName not in self.allStates:
            print("ERROR: addSetDummyTransition: state ", outStateName, " does not exist")
            sys.exit()
         for s in inStringSet:
            self.addTransition(inStateName, s, outString, outStateName)


    # map every element in inStirngSet to outString
    def addSetEpsilonTransition(self, inStateName, inStringSet, outStateName):
         if inStateName not in self.allStates:
            print("ERROR: addSetEpsilonTransition: state ", inStateName, " does not exist")
            sys.exit()
         if outStateName not in self.allStates:
            print("ERROR: addSetEpsionTransition: state ", outStateName, " does not exist")
            sys.exit()
         for s in inStringSet:
            self.addTransition(inStateName, s, "", outStateName)

    def parseInput(self, inString):
        SHOW_STATES = False#True
        inString = inString.rstrip('\n')
        (canParse, allParses)  = self.initState.parseInputFromStartState(inString)
        allParsesAsString = ""
        if canParse:
            for parse in allParses:
                for tuple in parse:
                    outString, outState = tuple
                    allParsesAsString += outString
                if SHOW_STATES:
                    allParsesAsString += "\t  States: "
                    i = 0
                    for tuple in parse:
                        i += 1
                        outString, outState = tuple
                        allParsesAsString += outState
                        if i < len(parse):
                            allParsesAsString += " => "
                    allParsesAsString += "; "

            return True, allParsesAsString
        else:
            return False, "FAIL"

    def printFST(self):
        print("Printing FST", str(self))
        for stateID in self.allStates:
            state = self.allStates[stateID]
            state.printState()

    def parseInputList(self, verbList):
        #with open(fileName, "r") as f:
        nParses = 0
        totalStrings = 0
        res = []
        for verb in verbList:#f:
            totalStrings += 1
            canParse, parse = self.parseInput(verb)
            res += [parse]
            if canParse:
                nParses += 1
        fraction = nParses/totalStrings
        print(nParses, "/", totalStrings, "=", str(fraction*100)+'%', "of examples parsed")
        return res

"""## Spanish transduction rule
<li><b>Stems ending in <TT>ñ</TT>:</b> If the stem ends in <TT>ñ</TT>, the ending is <TT>-ó</TT> rather than <TT>-ió</TT>:
<ul>
<TT>tañer ==> tañó&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gruñir ==> gruñó</TT>
</ul>
<em>Note:</em> This rule does <em>not</em> affect stems ending in regular <TT>n</TT>; it only affects stems in <T>ñ</TT> (<em>n</em> with a tilde).<br>
<li><b>Stems ending in a vowel:</b> If the stem ends in a vowel, the ending is <TT>-yó</TT> rather than <TT>-ió</TT>:
<ul>
<TT>leer ==> leyó&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;construir ==> construyó&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;corroer ==> corroyó</TT>
</ul>
<b>However</b>, this does <b>not</b> apply to verbs ending in <TT>-guir</TT> or <TT>-quir</TT> (which are regular).
<ul>
<TT>distinguir ==> distinguió&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;delinquir ==> delinquió</TT>
</ul>
<li> <b>Vowel raising:</b> For <TT>-ir</TT> verbs only, if the stem ends in an <TT>e</TT> followed by any number of consonants, then the <TT>e</TT> changes to an <TT>i</TT>:
<ul>
<TT>pedir ==> pidió&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;sentir ==> sintió&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;presentir ==> presintió</TT>
</ul>
This <b>also</b> applies to verbs ending in <TT>-eguir</TT>:
<ul>
<TT>seguir ==> siguió&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;conseguir ==> consiguió</TT>
</ul>
</ol>
"""

A2Z = set('abcçdefghijklmnopqrstuvwxyzáéíóúñü')
VOWS = set('aeiouáéíóúü')
CONS = A2Z-VOWS

def buildFST():

    # The states (you need to add more)
    f = FST('q1') # q1 is the initial (non-accepting) state
    f.addState('q_r')
    f.addState('q_epsilon')
    f.addState('q2')
    f.addState('q_vowels')
    f.addState('q_ñ')
    f.addState('q_etoi')
    f.addState('q_etoicon')
    f.addState('q_etoiconñ')
    # f.addState('q_g')
    f.addState('q_u')
    f.addState('q_vownote')
    f.addState('q_vownoteñ')
    f.addState('q_vownotecon')
    f.addState('q_notg')
    f.addState('q_g')
    f.addState('q_gu')
    f.addState('q_e')
    f.addState('q_eg')
    f.addState('q_egu')
    f.addState('q_note')
    f.addState('q_ee')
    f.addState('q_gg')
    f.addState('q_uu')

    f.addState('q_EOW', True) # An accepting state

    # SetTransition
    f.addSetTransition('q1', A2Z, 'q1')
    f.addSetTransition('q1', VOWS - {'e'}, 'q_vownote')
    f.addSetTransition('q1', CONS - {'ñ'}, 'q2')
    # f.addSetTransition('q1', VOWS, 'q_vowels')
    # f.addSetTransition('q1', A2Z - {'e'}, 'q_note')
    f.addSetTransition('q_vownote', CONS - {'ñ'}, 'q_vownotecon')
    f.addSetTransition('q_vownotecon', CONS - {'ñ'}, 'q_vownotecon')
    f.addSetTransition('q_etoi', CONS, 'q_etoi')
    f.addSetTransition('q_etoi', CONS - {'ñ'}, 'q_etoicon')
    f.addSetTransition('q1', A2Z - {'g', 'q'}, 'q_notg')
    f.addSetTransition('q_notg', VOWS, 'q_vowels')
    f.addSetTransition('q_g', VOWS - {'u'}, 'q_vowels')
    f.addSetTransition('q_note', {'g', 'q'}, 'q_g')
    f.addSetTransition('q1', A2Z - {'e'}, 'q_note')
    f.addSetTransition('q_gg', VOWS - {'u'}, 'q_vowels')
    # f.addSetTransition('q_notg', A2Z - {'g'}, 'q_notg')

    # SetTransition
    f.addTransition('q1', 'ñ', 'ñ', 'q_ñ')
    f.addTransition('q1', 'e', 'i', 'q_etoi')
    # f.addTransition('q_note', 'g', 'g', 'q_g')
    # f.addTransition('q_g', 'u', 'u', 'q_u')
    f.addTransition('q2', 'a', 'ó', 'q_r')
    f.addTransition('q2', 'e', 'ió', 'q_r')
    f.addTransition('q_ñ', 'a', 'ó', 'q_r')
    f.addTransition('q_ñ', 'e', 'ó', 'q_r')
    f.addTransition('q_etoi', 'ñ', 'ñ', 'q_etoiconñ')
    f.addTransition('q_vownote', 'ñ', 'ñ', 'q_vownoteñ')
    f.addTransition('q_vownotecon', 'i', 'ió', 'q_r')
    f.addTransition('q_vowels', 'a', 'ó', 'q_r')
    f.addTransition('q_vowels', 'e', 'yó', 'q_r')
    f.addTransition('q_vowels', 'i', 'yó', 'q_r')
    f.addTransition('q_etoicon', 'i', 'ió', 'q_r')
    f.addTransition('q_etoiconñ', 'i', 'ó', 'q_r')
    # f.addTransition('q_u', 'i', 'ió', 'q_r')
    f.addTransition('q_vownoteñ', 'i', 'ó', 'q_r')

    f.addTransition('q_g', 'u', 'u', 'q_gu')
    f.addTransition('q_gu', 'i', 'ió', 'q_r')
    f.addTransition('q_gu', 'a', 'ó', 'q_r')
    f.addTransition('q_gu', 'e', 'yó', 'q_r')

    f.addTransition('q1', 'e', 'i', 'q_e')
    f.addTransition('q_e', 'g', 'g', 'q_eg')
    f.addTransition('q_eg', 'u', 'u', 'q_egu')
    f.addTransition('q_egu', 'i', 'ió', 'q_r')

    f.addTransition('q1', 'e', 'e', 'q_ee')
    f.addTransition('q_ee', 'g', 'g', 'q_gg')
    f.addTransition('q_gg', 'u', 'u', 'q_uu')
    f.addTransition('q_uu', 'a', 'ó', 'q_r')
    f.addTransition('q_uu', 'e', 'yó', 'q_r')


    # Check the end of word

    f.addTransition('q_r', 'r', '', 'q_epsilon') # Transition on final r in infinitive - replace with 'ó' string
    f.addTransition('q_epsilon', '', '', 'q_EOW') # If see empty string, at end of word

    # Return completed FST
    return f

if __name__ == '__main__':
    testFST(print_examples='incorrect')