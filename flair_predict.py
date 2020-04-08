from flair.data import Sentence
from flair.models import SequenceTagger
import argparse, re, numpy as np, json
from collections import defaultdict

# parser = argparse.ArgumentParser(description="Train flair")
# parser.add_argument("--folder", type=str, help="folder to chkp")
# args = parser.parse_args()
# args = vars(args)
# tagger = SequenceTagger.load('./flair_models/'+args['folder']+'/final-model.pt')

model_num = '7'

tagger = SequenceTagger.load('./flair_models/score_'+model_num+'/final-model.pt') # load to gpu:0 by default, use CUDA_VISIBLE_DEVICES=x

data_source = 'biomed'
if data_source == 'TA1':
    postfix = ''
elif data_source == 'RPP':
    postfix = '_RPP'
elif data_source == 'biomed':
    postfix = '_biomed'

data, curr_data, curr_id = {}, [], None
with open("score/raw_all"+postfix+".txt", 'r') as f:
    f.readline()
    curr_id = f.readline()[:-1]
    while True:
        line = f.readline()
        if line in ["", "----NEW DOC----\n"]:
            assert curr_data
            data[curr_id] = curr_data
            curr_data = []
            if line == "":
                break
            curr_id = f.readline()[:-1]
        else:
            curr_data.append(line[:-1])

all_pred = {}
for id, sents in data.items():
    curr_pred = defaultdict(lambda: [])
    for sent in sents:
        sent = sent.split(' ')
        sentence = Sentence(' '.join(sent))
        _ = tagger.predict(sentence)
        pred_spans = sentence.get_spans('ner')
        for s in pred_spans:
            curr_pred[s.tag].append(s.text)
    
    all_pred[id] = dict(curr_pred)

# inspect predictions
all_types = list(set([rr for r in all_pred.values() for rr in r]))
type = 'PV'
all_mentions = []
for r in [r[type] for r in all_pred.values() if type in r]:
    for rr in r:
        all_mentions.append(rr)

ent = set(all_mentions)
for e in ent:
    print(e, '     ', process_pred(type, e))

# filter & normalize predictions
word2number = {'zero':0,'a':1,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,\
               'ten':10,'eleven':11,'twelve':12,'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,\
               'seventeen':17,'eighteen':18,'nineteen':19,'twenty':20,'thirty':30,'forty':40,'fifty':50,\
               'sixty':60,'seventy':70,'eighty':80,'ninety':90,'hundred':100,'thousand':1000,'million':1000000}

def text2number(text):
    l = re.split('-| ', text)
    base = None
    for r in l:
        if r in ['hundred', 'thousand', 'million']:
            if base == None:
                base = 1
            base *= word2number[r]
        elif r in word2number:
            if base == None:
                base = word2number[r]
            else:
                base += word2number[r]
        elif r == 'and':
            if base == None:
                return None
        else:
            # if a number exists, return it. It not detected any number, continue (may be some leading trivial words)
            if base:
                return base
    
    return base

def read_list_numbers(l, min_, max_):
    result, counter = [], 0
    for r in l:
        if r == ',':
            continue
        try:
            number = float(r)
            if number >= max_ or number <= min_:
                continue
            result.append(number)
        except:
            try:
                r1 = re.findall('[-\.0-9]+', r)[0]
                r2 = '.'.join(r1.split('.')[:2])
                number = float(r2)
                if number >= max_ or number <= min_:
                    continue
                result.append(number)
            except:
                counter += 1
                if counter > 1:
                    break
    
    return result

def process_pred(type, pred):
    pred = pred.strip()
    pred = pred.replace('−', '-')
    result = []
    if type == 'ES':
        pred_split = pred.split(' ')
        if len(pred_split) < 2:
            return None
        if pred_split[0] == 'r':
            if pred_split[1] == '2':
                if len(pred_split) < 3:
                    return None
                tag = 'R2'
                for i in range(2, min(len(pred_split), 10)):
                    try:
                        number = float(re.findall('[-\.0-9]+', pred_split[i])[0])
                        if 0 < number < 1:
                            result = read_list_numbers(pred_split[i:], 0, 1)
                            break
                    except:
                        continue
            elif pred_split[1] == ')':
                return None
            elif pred_split[1] == '(':
                tag = 'r'
                for i in range(2, min(len(pred_split), 6)):
                    try:
                        number = float(re.findall('[-\.0-9]+', pred_split[i])[0])
                        if -1 < number < 1:
                            result = read_list_numbers(pred_split[i:], -1, 1)
                            break
                    except:
                        continue
            else:
                tag = 'r'
                for i in range(0, min(len(pred_split), 6)):
                    try:
                        number = float(re.findall('[-\.0-9]+', pred_split[i])[0])
                        if -1 < number < 1:
                            result = read_list_numbers(pred_split[i:], -1, 1)
                            break
                    except:
                        continue
        elif 'r2' in pred_split[0] or 'r-squared' in pred_split[0] or pred_split[:2] == ['adjusted', 'r2']:
            tag = 'R2'
            for i in range(0, min(len(pred_split), 6)):
                try:
                    number = float(re.findall('[-\.0-9]+', pred_split[i])[0])
                    if 0 < number < 1:
                        result = read_list_numbers(pred_split[i:], 0, 1)
                        break
                except:
                    continue
        
        else:
            return None
        
        if result:
            return tag, result
    
    elif type == 'PV':
        pred_split = pred.split(' ')
        if '*' in pred_split[0]:
            return None
        if 'p' in pred_split[0] and (len(pred_split[0]) < 3 or re.findall('[-\.0-9]+', pred_split[0])):
            tag = 'p'
            for i in range(0, min(len(pred_split), 5)):
                try:
                    r1 = re.findall('[-\.0-9]+', pred_split[i])[0]
                    r2 = '.'.join(r1.split('.')[:2])
                    number = float(r2)
                    if 0 < number < 1:
                        result = read_list_numbers(pred_split[i:], 0, 1)
                        break
                except:
                    continue
        
        if result:
            return tag, result
    
    elif type == 'SS':
        pred = pred.replace(',', '')
        pred_split = pred.split(' ')
        try:
            number = int(pred_split[0])
            return number
        except:
            pass
        
        # number = text2number(pred_split[0])
        number = text2number(pred)
        if number:
            return number
    
    elif type in ['SD', 'TE']:
        name = pred.split(' ')[0]
        if not ('stud' in name or 'experiment' in name or 'model' in name or 'result' in name):
            return None
        numbers = [int(r) for r in re.findall('\d+', pred)]
        numbers = [n for n in numbers if n < 15]
        if numbers:
            return max(numbers)
    
    elif type == 'TN':
        pred = pred.replace('- ', '')
        return pred
    
    return None


output = {}
for id, preds in all_pred.items():
    curr_output = {}
    
    if 'SS' in preds:
        processed = [process_pred('SS', r) for r in preds['SS']]
        processed = [r for r in processed if r]
        curr_output['Sample Sizes'] = list(set(processed))
    else:
        curr_output['Sample Sizes'] = None
    
    if 'TN' in preds:
        processed = [process_pred('TN', r) for r in preds['TN']]
        processed = set([r for r in processed if r])
        processed = sorted(processed, key=lambda x:len(x), reverse=True)
        processed = [[r, set(re.findall('[^-^\s]+', r))] for r in processed]
        for i in range(1, len(processed)):
            for j in range(0,i):
                if processed[j] is None:
                    continue
                if processed[i][1].issubset(processed[j][1]):
                    processed[i] = None
                    break
        
        processed = [r[0] for r in processed if r]
        curr_output['Model Names'] = processed
    else:
        curr_output['Model Names'] = None
    
    if 'TE' in preds:
        processed = [process_pred('TE', r) for r in preds['TE']]
        processed = [r for r in processed if r]
        if processed:
            curr_output['Number of Models/Tests'] = max(processed)
        else:
            curr_output['Number of Models/Tests'] = None
    else:
        curr_output['Number of Models/Tests'] = None
    
    if 'SD' in preds:
        processed = [process_pred('SD', r) for r in preds['SD']]
        processed = [r for r in processed if r]
        if processed:
            curr_output['Number of Studies'] = max(processed)
        else:
            curr_output['Number of Studies'] = None
    else:
        curr_output['Number of Studies'] = None
    
    if 'PV' in preds:
        processed = [process_pred('PV', r) for r in preds['PV']]
        processed = [r for r in processed if r]
        processed = [r for rr in processed for r in rr[1]]
        curr_output['P Values'] = processed
    else:
        curr_output['P Values'] = None
    
    if 'ES' in preds:
        processed = [process_pred('ES', r) for r in preds['ES']]
        processed = [r for r in processed if r]
        r = [x for x in processed if x[0] == 'r']
        R2 = [x for x in processed if x[0] == 'R2']
        r = [x for xx in r for x in xx[1]]
        R2 = [x for xx in R2 for x in xx[1]]
        if r:
            curr_output['Effect Sizes - r'] = r
        else:
            curr_output['Effect Sizes - r'] = None
        if R2:
            curr_output['Effect Sizes - R2'] = R2
        else:
            curr_output['Effect Sizes - R2'] = None
    else:
        curr_output['Effect Sizes - r'] = None
        curr_output['Effect Sizes - R2'] = None
    
    output[id] = curr_output


# inspect final results
# id = '8wZ0'
# for r in output[id].items():
    # print(r)

# for r in all_pred[id].items():
    # print(r)


# write to file
with open("./flair_pred/extraction_result_"+model_num+postfix+".csv", 'w') as f:
    f.write('Paper ID,Sample Sizes,Model Names,Number of Models/Tests,'
            'Number of Studies,P Values,Effect Sizes - r,Effect Sizes - R2\n')
    for id, out in output.items():
        SS = str(out['Sample Sizes']) if out['Sample Sizes'] else 'None'
        TN = str(out['Model Names']).replace('"', '') if out['Model Names'] else 'None'
        # TN = TN.replace(',', '')
        TE = str(out['Number of Models/Tests']) if out['Number of Models/Tests'] else 'None'
        SD = str(out['Number of Studies']) if out['Number of Studies'] else 'None'
        PV = str(out['P Values']) if out['P Values'] else 'None'
        ESr = str(out['Effect Sizes - r']) if out['Effect Sizes - r'] else 'None'
        ESR2 = str(out['Effect Sizes - R2']) if out['Effect Sizes - R2'] else 'None'
        f.write('"'+id+'","'+SS+'","'+TN+'","'+TE+'","'+SD+'","'+PV+'","'+ESr+'","'+ESR2+'"\n')

json.dump(output, open("./flair_pred/extraction_result_"+model_num+postfix+".json", 'w'))

