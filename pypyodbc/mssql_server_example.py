'''
    Test communication to Microsoft SQL Server, Trusted Connections, etc
    Installing the SQL Server Management Tools (SSMS) on a Windows system might be
        necessary in order to get the "SQL Server" driver installed

        For the example to work, you'd need to create a database called batch_stock_quotes
            and run this code in it (from SSMS), or change the database name in the
            code below

        Make sure when you are sending in data elements that you match the python
            data type to the element you are trying to match.

            integers should be coerced from string format with int(mystring)
            numeric or floats should be coerced from string format with float(mystring)
            datetimes should be coerced with datetime.strptime(mystring,'%Y-%m-%d')
                While using the correct formatting for your date format.  The one above
                handles something like (2018-06-12) -- aka June 12, 2018

        Example Table (SQL Server 12 AKA 2014) and 1 data row:

        CREATE TABLE [dbo].[daily_close_prices](
        	[ticker] [varchar](6) NOT NULL,
        	[close_date] [datetime] NOT NULL,
        	[close] [numeric](18, 6) NOT NULL,
         CONSTRAINT [PK_daily_close_prices] PRIMARY KEY CLUSTERED
        (
        	[ticker] ASC,
        	[close_date] ASC
        )WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON) ON [PRIMARY]
        ) ON [PRIMARY]
        GO

        INSERT INTO [dbo].[daily_close_prices]
                   ([ticker]
                   ,[close_date]
                   ,[close])
             VALUES
                   ('INTC'
                   ,'2018-06-08 00:00:00.000'
                   ,53.220000)
        GO


'''
import pprint
import pypyodbc


QUERY_TIMEOUT = 10
CONNECTION_TIMEOUT = 5
SERVER = 'sqlservername,1433'

def run(server=None, database=None, user_and_pw=None, query=None, query_params=None):
    '''
        run sample query against database
    '''
    dsn = 'DRIVER={SQL Server};SERVER='+server+';DATABASE='+database+';' + user_and_pw + ';'

    #default the timeouts to the global timeouts, but you can alter them
    results = query_sql(conn_string=dsn,
                        query=query,
                        query_params=query_params,
                        conn_timeout=CONNECTION_TIMEOUT,
                        query_timeout=QUERY_TIMEOUT)

    if results:
        p_p = pprint.PrettyPrinter(indent=1)
        p_p.pprint(results)
        #print(results)

    else:
        print(query, '0 results')

def query_sql(conn_string=None, query=None, query_params=None,
              query_timeout=QUERY_TIMEOUT, conn_timeout=CONNECTION_TIMEOUT):
    '''
        Call MS SQL - Tested with MS SQL 2014, and Trusted Connections
    '''

    pypyodbc.connection_timeout = conn_timeout #connect timeout

    conn = pypyodbc.connect(conn_string)
    cursor = conn.cursor()
    cursor.set_timeout(query_timeout)  #query timeout

    #cursor.autocommit = True  #dont make me run a commit after exery execute - doesnt work

    if not query_params:
        cursor.execute(query)
    else:
        cursor.execute(query, query_params)

    if cursor.description:
        #some queries return no results, .description will be empty if this is the case
        # we are not talking about select * from this where that = 0 and nothing matches
        #  instead, "exec spDoSomething" updates some data, deletes some other data and returns
        query_results = [dict(zip([column[0] for column in cursor.description], row)) \
            for row in cursor.fetchall()]
        #from a performance standpoint, fetchall might not be the most ideal solution
        #  in every case, however, for testing purposes, we'll let it slide
    else:
        query_results = []
    
    cursor.commit()

    cursor.close()

    if conn.connected:
        conn.close()

    return query_results

if __name__ == '__main__':
    '''
        user_and_pw='Trusted_Connections=Yes'
            allows you to use the currently logged in user's credentials

        You could use this as well:
            user_and_pw=UID='userName';PWD='Password'

        expected output:
            INTC
            [{'ticker': 'INTC'}]
            MSFT
            select top 1 ticker from daily_close_prices where ticker = ? 0 results
            spDoSomething
            exec spDoSomething 0 results
    '''

    #if you created the table above and ran the insert, you would have a cursor.description and 1 row to return
    print('INTC')
    run(server=SERVER,
        database='stock_quotes',
        user_and_pw='Trusted_Connections=Yes',
        query='select top 1 ticker from daily_close_prices where ticker = ?',
        query_params=['INTC'])

    print('MSFT')
    #no data in table for MSFT, so this would return 0 results, but would have a cursor.description
    run(server=SERVER,
        database='stock_quotes',
        user_and_pw='Trusted_Connections=Yes',
        query='select top 1 ticker from daily_close_prices where ticker = ?',
        query_params=['MSFT'])

    '''
        something that doesnt return a resultset
        (possibly an insert or update statement, or procedure designed to perform
        an operation on data but not return results)

        Example:

            CREATE PROCEDURE [dbo].[spDoSomething]
            AS
            declare @this int
            set @this = '123456'
            --set statements dont return results
            GO
    '''
    print('spDoSomething')
    run(server=SERVER,
        database='stock_quotes',
        user_and_pw='Trusted_Connections=Yes',
        query='exec spDoSomething')
