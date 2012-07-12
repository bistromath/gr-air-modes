
#so, not to be a dick or anything, but this thing could be entirely
#replaced with a clever SQL join or just a separate SQL table flattened
#in modes_sql and designed specifically for this. you can keep the older
#ones, too. this would let you access indices by column name, too. bonus.
#you wouldn't get the nice hierarchical tree view, though. what does that lose you?
#you'd need a different datamodel for the tree view, that's all.
class modes_datamodel(QtCore.QAbstractItemModel):
    def __init__(self, db):
        QtCore.QAbstractItemModel.__init__(self)
        self.db = db
        
    def rowCount(self, parent=QtCore.QModelIndex()):
        icaoquery = "select count(distinct icao) from positions"
        query = QtSql.QSqlQuery()
        query.exec_(icaoquery)
        query.next()
        return query.value(0).toInt()[0]
                
    def columnCount(self, parent=QtCore.QModelIndex()):
        return 5

    #for future use
    def flags(self, index):
        return QtCore.QAbstractItemModel.flags(self, index)
    
    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return QtCore.QVariant()
        if index.row() >= self.rowCount():
            return QtCore.QVariant()
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            #get ICAO of current index
            query = QtSql.QSqlQuery()
            #TODO: limit this to aircraft seen in last 600 seconds? or make a spinbox for this limit.
            icaoquery = "select distinct icao from positions order by icao limit %i,1" % index.row()
            query.exec_(icaoquery)
            query.next()
            icao = query.value(0).toInt()[0]
            #TODO figure out how to grab multiple records in one query and return them all?
            if index.column() == 0: #ICAO
                return "%06x" % icao
            elif index.column() == 1: #last seen
                seenquery = "select seen from positions where icao = %i order by seen desc limit 1" % icao
                query.exec_(seenquery)
                return "" if query.next() is False else query.value(0).toString()
            elif index.column() == 2: #ident
                identquery = "select ident from ident where icao = %i" % icao
                query.exec_(identquery)
                return "" if query.next() is False else query.value(0).toString()
            elif index.column() == 3: #altitude
                querystr = "select alt from positions where icao = %i order by seen desc limit 1" % icao
                query.exec_(querystr)
                return "" if query.next() is False else "%i" % query.value(0).toInt()[0]
            elif index.column() == 4: #latitude
                querystr = "select lat from positions where icao = %i order by seen desc limit 1" % icao
                query.exec_(querystr)
                return "" if query.next() is False else "%.6f" % query.value(0).toFloat()[0]
            elif index.column() == 5: #longitude
                querystr = "select lon from positions where icao = %i order by seen desc limit 1" % icao
                query.exec_(querystr)
                return "" if query.next() is False else "%.6f" % query.value(0).toFloat()[0]

        else:
            return QtCore.QVariant()

    def index(self, row, column, parent=QtCore.QModelIndex()):
        return self.createIndex(row, column)

    def parent(self, child):
        return QtCore.QModelIndex()
