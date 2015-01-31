#this file holds the classes used to create the A&D reports using the HMDA LAR files combined with Census demographic information

class AD_report(object):
    def __init__(self):
        pass

class report_selector(AD_report):
    pass

class set_race(AD_report):
    pass
    #store FFIEC codes




class parse_inputs(AD_report):
    #needs to take all the variables used in all the reports
    #use if exists logic to pass in a row and parse it to a dictionary
    #does this require standardization of the SQL query to return the same string?
    #check the psycopg2.extras docs on dictcursor
    inputs = {}

    def parse_t31(self, row): #takes a row from a table 3-1 query and parses it to the inputs dictionary (28 tuples)
        #parsing inputs for report 3.1
        #self.inputs will be returned to for use in the aggregation function
        #instantiate classes to set loan variables
        MSA_index = MSA_info()
        demo=demographics()
        #race lists will hold 5 integers
        a_race = []
        co_race = []
        #fill race lists from the demographics class
        a_race = demo.co_race_list(row)
        co_race = demo.a_race_list(row)

        #add data elements to dictionary
        self.inputs['a ethn'] = row['applicantethnicity']
        self.inputs['co ethn'] = row['co_applicantethnicity']
        self.inputs['income'] = row['applicantincome']
        self.inputs['rate spread'] = row['ratespread']
        self.inputs['lien status'] = row['lienstatus']
        self.inputs['hoepa flag'] = row['hoepastatus']
        self.inputs['purchaser'] = int(row['purchasertype'])
        self.inputs['loan value'] = float(row['loanamount'])
        self.inputs['sequence'] = row['sequencenumber'] # the sequence number to track loans in error checking
        self.inputs['year'] = row['asofdate']
        self.inputs['state code'] = row['statecode']
        self.inputs['state name'] = row['statname']
        self.inputs['census tract'] = row['censustractnumber'] # this is currently the 7 digit tract used by the FFIEC, it includes a decimal prior to the last two digits
        self.inputs['county code'] = row['countycode']
        self.inputs['county name'] = row['countyname']
        self.inputs['MSA median income'] = row['ffiec_median_family_income']
        self.inputs['minority percent'] = row['minoritypopulationpct']
        self.inputs['tract to MSA income'] = row['tract_to_msa_md_income']
        self.inputs['tract income index'] = MSA_index.tract_to_MSA_income(self.inputs)
        self.inputs['income bracket'] = MSA_index.app_income_to_MSA(self.inputs)
        self.inputs['minority percent'] = MSA_index.minority_percent(self.inputs)
        self.inputs['tract income index'] = MSA_index.tract_to_MSA_income(self.inputs)
        self.inputs['app non white flag'] = demo.set_non_white(a_race)
        self.inputs['co non white flag'] = demo.set_non_white(co_race)
        self.inputs['joint status'] = demo.set_joint(self.inputs) #requires non white status flags be set prior to running set_joint
        self.inputs['minority status'] = demo.set_minority_status(self.inputs) #requires non white flags be set prior to running set_minority_status
        self.inputs['ethnicity'] = demo.set_loan_ethn(self.inputs) #requires  ethnicity be parsed prior to running set_loan_ethn
        self.inputs['race'] = demo.set_race(self.inputs, a_race, co_race) #requires joint status be set prior to running set_race
    #loop over all elements in both race lists to flag presence of minority race
    #assigning non-white boolean flags for use in joint race status and minority status checks
    #set boolean flag for white/non-white status for applicant
    #need to check App A ID2 for race 6

class demographics(AD_report):
    #holds all the functions for setting race, minority status, and ethnicity for FFIEC A&D reports

    #set race_code to integers for use in JSON structure lists
    #American Indian/Alaska Native or 1 indexed at 0
    #Asian or 2 indexed at 1
    #Black or 3 indexed at 2
    #Pacific Islander or 4 indexed at 3
    #White or 5 indexed at 4
    #Not Provided indexed at 5
    #Not Applicable indexed at 6
    #2 minority indexed 7
    #joint indexed 8
    #not reported indexed 9
    def minority_count(self, a_race):
        #the minority count is the count of minority races listed for the primary applicant
        minority_count = 0
        for race in a_race:
            if race < 5 and race > 0:
                minority_count += 1
        return minority_count

    def set_non_white(self, race_list): #pass in a list of length 5, return a boolean
        for i in range(0,5):
            if race_list[i] < 5 and race_list[i] != 0:
                return True #flag true if applicant listed a minority race
                break
            elif race_list[i] == 5:
                return False #flag false if the only race listed was white (5)

    def set_joint(self, inputs): #takes a dictionary 'inputs' which is held in the controller(?) object and used to process each loan row
        #joint status exists if one borrower is white and one is non-white
        #check to see if joint status exists
        if inputs['app non white flag'] == False and inputs['co non white flag'] == False:
            return False #flag false if both applicant and co-applicant are white
        elif inputs['app non white flag'] == True and inputs['co non white flag'] == True:
            return False #flag false if both applicant and co-applicant are minority
        elif inputs['app non white flag'] == True and inputs['co non white flag'] ==  False:
            return True #flag true if one applicant is minority and one is white
        elif inputs['app non white flag'] == False and inputs['co non white flag'] == True:
            return True #flag true if one applicant is minority and one is white

    def set_minority_status(self, inputs):
        #determine minority status
        #if either applicant reported a non-white race or an ethinicity of hispanic or latino then minority status is true
        if inputs['app non white flag'] == True or inputs['co non white flag'] == True or inputs['a ethn'] == '1' or inputs['co ethn'] == '1':
            return  1
        #if both applicants reported white race and non-hispanic/latino ethnicity then minority status is false
        elif inputs['app non white flag'] != True and inputs['co non white flag'] != True and inputs['a ethn']  != '1' and inputs['co ethn'] != '1':
            return 0
        else:
            print 'minority status not set'

    #this function outputs a number code for ethnicity: 0 - hispanic or latino, 1 - not hispanic/latino
    #2 - joint (1 applicant hispanic/latino 1 not), 3 - ethnicity not available
    def set_loan_ethn(self, inputs):
        #if both ethnicity fields are blank report not available(3)
        if inputs['a ethn'] == ' ' and inputs['co ethn'] == ' ':
            return  3 #set to not available

        #determine if the loan is joint hispanic/latino and non hispanic/latino(2)
        elif inputs['a ethn'] == '1' and inputs['co ethn'] != '1':
            return  2 #set to joint
        elif inputs['a ethn'] != '1' and inputs['co ethn'] == '1':
            return  2 #set to joint

        #determine if loan is of hispanic ethnicity (appplicant is hispanic/latino, no co applicant info or co applicant also hispanic/latino)
        elif inputs['a ethn'] == '1' and inputs['co ethn'] == '1':
            return  0
        elif inputs['a ethn'] == '1' and (inputs['co ethn'] == ' ' or inputs['co ethn'] == '3' or inputs['co ethn'] == '4' or inputs['co ethn']== '5'):
            return  0
        elif (inputs['a ethn'] == ' ' or inputs['a ethn'] == '3' or inputs['a ethn'] == '4' or inputs['a ethn'] == '5') and inputs['co ethn'] == '1':
            return  0
        #determine if loan is not hispanic or latino
        elif inputs['a ethn'] == '2' and inputs['co ethn'] != '1':
            return  1
        elif inputs['a ethn'] != '1' and inputs['co ethn'] == '2':
            return  1
        elif (inputs['a ethn'] == '3' or inputs['a ethn'] == '4') and (inputs['co ethn'] != '1' and inputs['co ethn'] != '2'):
            return  3
        else:
            print "error setting ethnicity"

    def a_race_list(self, row):
        #filling the loan applicant race code lists (5 codes per applicant)
        a_race = [race for race in row[1:6]]

        #convert ' ' entries to 0 for easier comparisons and loan aggregation
        for i in range(0, 5):
            if a_race[i] == ' ':
                a_race[i] = 0
        #convert string entries to int for easier comparison and loan aggregation
        return [int(race) for race in a_race]

    def co_race_list(self, row):
        #filling the loan co-applicant race code lists (5 codes per applicant)
        co_race = [race for race in row[6:11]]
        for i in range(0,5):
            if co_race[i] == ' ':
                co_race[i] = 0
        #convert string entries to int for easier comparison and loan aggregation

        return [int(race) for race in co_race]

    def set_race(self, inputs, a_race, co_race):
        #inputs is a dictionary, a_race and co_race are 5 element integer lists
        #if one white and one minority race are listed, use the minority race
        #race options are: joint, 1 through 5, 2 minority, not reported
        #if the entry is 'joint' then the loan is aggregated as 'joint'
        #create a single race item instead of a list to use in comparisons to build aggregates

        if inputs['joint status'] == True:
            return  8
        #determine if the loan will be filed as 'two or more minority races'
        #if two minority races are listed, the loan is 'two or more minority races'
        #if any combination of two or more race fields are minority then 'two or more minority races'
        elif self.minority_count(a_race) > 1:
            return  7

        #if only the first race field is used, use the first filed
        elif a_race[0] != 0 and a_race[1] == 0 and a_race[2] == 0 and a_race[3] == 0 and a_race[4] == 0:
            return  a_race[0] #if only one race is reported, and joint status and minority status are false, set race to first race

        elif a_race[0] == 0 and a_race[1] == 0 and a_race[2] == 0 and a_race[3] == 0 and a_race[4] == 0:
            return  9 #if all race fields are blank, set race to 'not reported'

        else:
            #does this code work for minority co applicants with non-minority applicants?
            for i in range(1,5):
                if i in a_race: #check if a minority race is present in the race array
                    return  a_race[0]
                    if a_race[0] == 5:
                        for code in a_race:
                            if code < 5 and code != 0: #if first race is white, but a minority race is reported, set race to the first minority reported
                                return  code
                                break #exit on first minority race


class build_JSON(AD_report):
    pass

class connect_DB(AD_report):
#I'm not sure how to pass the cursor object back to the controller object
    def connect(self):
        import psycopg2
        import psycopg2.extras
        from collections import OrderedDict

        with open('/Users/roellk/Desktop/python/credentials.txt', 'r') as f:
            credentials = f.read()

        cred_list = credentials.split(',')
        dbname = cred_list[0]
        user = cred_list[1]
        host = cred_list[2]
        password = cred_list[3]

        #set a string for connection to SQL
        connect_string = "dbname=%s user=%s host=%s password =%s" %(dbname, user, host, password)

        try:
            conn = psycopg2.connect(connect_string)
            print "i'm connected"
        #if database connection results in an error print the following
        except:
            print "I am unable to connect to the database"

        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)


class MSA_info(AD_report):

    def app_income_to_MSA(self, inputs):
        #set income bracket index
        if inputs['income'] != 'NA  ' or inputs['income'] != '    ':
            inputs['income bracket'] = 5
        elif inputs['MSA median income'] != 'NA      ' and inputs['MSA median income'] != '        ' :
            inputs['income bracket'] = 6 #placeholder for MSA median income unavailable
        else:
            inputs['percent MSA income'] = float(inputs['income']) / float(inputs['MSA median income'] )
            #determine income bracket for use as an index in the JSON object
            #move this somewhere else
            #check logic on math to make sure all is inclusive - set a rounding function on line 71
            if inputs['percent MSA income'] < 50:
                return 0
            elif inputs['percent MSA income'] <= 79:
                return 1
            elif inputs['percent MSA income'] <= 99:
                return 2
            elif inputs['percent MSA income'] <= 119:
                return 3
            elif inputs['percent MSA income'] >= 120:
                return 4
            else:
                print 'error setting percent MSA income bracket for index'

    def minority_percent(self, inputs):
        #set index codes for minority population percent
        if inputs['minority percent'] == '      ' or inputs['minority percent'] == 'NA    ':
            return  4
        elif float(inputs['minority percent']) < 10:
            return  0
        elif float(inputs['minority percent'])  <= 49:
            return  1
        elif float(inputs['minority percent'])  <= 79:
            return  2
        elif float(inputs['minority percent'])  <= 1:
            return  3
        else:
            print "minority percent index not set"

    def tract_to_MSA_income(self, inputs):
        #set census MSA income level: low, moderate, middle, upper
        if inputs['tract to MSA income'] < 50:
            return 0
        elif inputs['tract to MSA income'] < 80:
            return 1
        elif inputs['tract to MSA income'] < 120:
            return 2
        elif inputs['tract to MSA income'] >=120:
            return 3
        else:
            print "error setting tract to MSA income index"

class queries(AD_report):

    def table_3_1(self):
        #set the SQL statement to select the needed fields to aggregate loans for the table_3 JSON structure
        SQL = '''SELECT
            censustractnumber, applicantrace1, applicantrace2, applicantrace3, applicantrace4, applicantrace5,
            coapplicantrace1, coapplicantrace2, coapplicantrace3, coapplicantrace4, coapplicantrace5,
            applicantethnicity, co_applicantethnicity, applicantincome, ratespread, lienstatus, hoepastatus,
            purchasertype, loanamount, sequencenumber, asofdate, statecode, statname, countycode, countyname,
            ffiec_median_family_income, minoritypopulationpct, tract_to_msa_md_income
            FROM hmdapub2012 WHERE msaofproperty = %s;'''
        return SQL
