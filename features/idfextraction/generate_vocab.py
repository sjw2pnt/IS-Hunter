from sklearn.feature_extraction.text import CountVectorizer
from features.data_helper import *
import xlrd

def generate_vocab(data):#输入字符串，返回将字符串中的单词分割之后形成的字典

    # count_vect = CountVectorizer(stop_words='english')
    count_vect = CountVectorizer(tokenizer=tokenizer, stop_words='english')
    counts = count_vect.fit_transform(data)

    return count_vect.vocabulary_

if __name__ == '__main__':
    # conn_title = connect_db()
    # conn_utter = connect_db()
    #
    # sql_title = 'select title from titles_final'
    # sql_utter = 'select utterance from contents_final'
    #
    # with conn_title.cursor() as cursor_title, conn_utter.cursor() as cursor_utter:
    #     cursor_title.execute(sql_title)
    #     titles = [row['title'] for row in cursor_title.fetchall()]
    #
    #     cursor_utter.execute(sql_utter)
    #     utterances = [row['utterance'] for row in cursor_utter.fetchall()]

    vocab_file = '../../data/vocab.tsv'
    projects = ['Angular','Appium', 'Deeplearning4j', 'Docker', 'Ethereum', 'Nodejs', 'Gitter', 'Typescript']
    remark_pos = [6, 6, 7, 6, 6, 6, 6, 6]#在表格对应的标记为写个“1”可以避免报指针越界的错误
    utterances = []
    for project, remark in zip(projects, remark_pos):
        workbook = xlrd.open_workbook('../../data/data.xls')#存放话语数据的表格文件对象
        sheet = workbook.sheet_by_name(project)#xls中的一张表格，名字为project
        # print(sheet.nrows)
        data_utterances = sheet.col_values(1, 0, sheet.nrows)#返回一个列表，第[1]列，从第[0]行到第[nrow]行
        # print(data_utterances[0])
        data_remarks = sheet.col_values(remark, 0, sheet.nrows)
        # print(data_remarks[0])
        for data_utterance, data_remark in zip(data_utterances, data_remarks):
            if data_remark != '' or data_utterance == '':#话语若被标记，则continue
                continue
            conversation = data_utterance.split('\n')#将话语按照换行符进行分裂，返回一个列表
            conversation = [each_utterance[each_utterance.index('>') + 1:] for each_utterance in conversation if '>' in each_utterance]
            #推测是利用[<-LINK->]中的>作为标记，选出话语中在<-LINK->之后的文本
            utterances += conversation#将满足条件的conversation加入到utterances列表中
    vocab = generate_vocab(map(clean_str, utterances))#titles + utterances

    with open(vocab_file, 'w') as vocab_output:
        for term in vocab:
            vocab_output.write('{0}\t{1}\n'.format(term, vocab[term]))#循环依次将 单词\t（\t在表格中相当于换下一格）单词对应的值\n （\n换行）写入文件