--  select * from udfConvertSize(2000, 'GB')
--  select * from udfConvertSize(2000, 'MB')
--  select * from udfConvertSize(15000000, 'KB')

CREATE FUNCTION [dbo].[udfConvertSize] (
  @size numeric(30, 2), -- size as a number of given type ex. 5400
  @size_type char(2) -- KB, MB, GB, TB, PB, EB
)
RETURNS @table TABLE (
    [kb] numeric(30,2),
    [mb] numeric(30,2),
    [gb] numeric(30,2),
    [tb] numeric(30,2),
    [pb] numeric(30,2),
    [eb] numeric(30,2),
    [val] numeric(30,2),
    [type] varchar(2),
    [string] varchar(33))
AS
BEGIN
	/*
		CREATE DATE: 07/05/2022

		Description:  Convert a size from one format to another, and give out other values as well
                     ** If you have a value always outputting in KB (or MB, GB, TB, PB, EB), and you want it in friendly format,
                        this does the conversion for you:
                          2097152000 KB  -> 1.95TB
		              This is a Multi-statement Table-valued Function for Microsoft SQL Server (tested in SQL 2019)
	*/

	declare @my_size numeric(30,2)
	set @my_size = @size
	declare @kb_unit numeric(30,2)
	set @kb_unit = 1024

	IF @size_type = 'KB'
		set @my_size = @my_size
	ELSE IF @size_type = 'MB'
		set @my_size = @my_size * POWER(@kb_unit,1)
	ELSE IF @size_type = 'GB'
		set @my_size = @my_size * POWER(@kb_unit, 2)
	ELSE IF @size_type = 'TB'
		set @my_size = @my_size * POWER(@kb_unit, 3)
	ELSE IF @size_type = 'PB'
		set @my_size = @my_size * POWER(@kb_unit, 4)
	ELSE IF @size_type = 'EB'
		set @my_size = @my_size * POWER(@kb_unit, 5)
	--ENDIF
    -- inserts 1 row: 
	--       EXAMPLE of (2000, 'GB'): kb (2097152000.00) , mb (2048000.00), gb (2000.00), tb (1.95), pb (0.00), eb (0.00), val (1.95), type (TB), string (1.95TB)
	INSERT @table
	SELECT  convert(numeric(30, 2), @my_size) as kb,
			convert(numeric(30, 2), @my_size / POWER(@kb_unit, 1)) as mb,
			convert(numeric(30, 2), @my_size / POWER(@kb_unit, 2)) as gb,
			convert(numeric(30, 2), @my_size / POWER(@kb_unit, 3)) as tb,
			convert(numeric(30, 2), @my_size / POWER(@kb_unit, 4)) as pb,
			convert(numeric(30, 2), @my_size / POWER(@kb_unit, 5)) as eb,

			CASE WHEN @my_size / power(@kb_unit, 4) >= 1024 THEN convert(numeric(30, 2), @my_size / power(@kb_unit, 5))
				 WHEN @my_size / power(@kb_unit, 3) >= 1024 THEN convert(numeric(30, 2), @my_size / power(@kb_unit, 4))
				 WHEN @my_size / power(@kb_unit, 2) >= 1024 THEN convert(numeric(30, 2), @my_size / power(@kb_unit, 3))
				 WHEN @my_size / 1024 >= power(@kb_unit, 1) THEN  convert(numeric(30, 2), @my_size / power(@kb_unit, 2))
				 WHEN @my_size >= power(@kb_unit, 1) THEN convert(numeric(30, 2), @my_size / power(@kb_unit, 1))
				 ELSE convert(numeric(30, 2), @my_size)
				 END as val,
			CASE WHEN @my_size / 1024 / 1024 / 1024 / 1024 >= 1024 THEN 'EB'
				 WHEN @my_size / 1024 / 1024 / 1024 >= 1024 THEN 'PB'
				 WHEN @my_size / 1024 / 1024 >= 1024 THEN 'TB'
				 WHEN @my_size / 1024 >= 1024 THEN 'GB' 
				 WHEN @my_size >= 1024 THEN 'MB' 
				 ELSE 'KB' END AS [type],
			CASE WHEN @my_size / 1024 / 1024 / 1024 / 1024 >= 1024 THEN convert(varchar(20), convert(numeric(30, 2), @my_size / power(@kb_unit, 5))) + 'EB'
				 WHEN @my_size / 1024 / 1024 / 1024 >= 1024 THEN convert(varchar(20),  convert(numeric(30, 2), @my_size / power(@kb_unit, 4))) + 'PB'
				 WHEN @my_size / 1024 / 1024 >= 1024 THEN convert(varchar(20), convert(numeric(30, 2), @my_size / power(@kb_unit, 3))) + 'TB'
				 WHEN @my_size / 1024 >= 1024 THEN convert(varchar(20), convert(numeric(30, 2), @my_size / power(@kb_unit, 2))) + 'GB' 
				 WHEN @my_size >= 1024 THEN convert(varchar(20), convert(numeric(30, 2), @my_size / power(@kb_unit, 1))) + 'MB' 
				 ELSE  convert(varchar(20), convert(numeric(30, 2), @my_size)) + 'KB' END AS [string]
	RETURN
END
