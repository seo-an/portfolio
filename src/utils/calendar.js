// Basic Settings
const dateToString = ( year, month, date ) => {
	// console.log('dateToString', year, month, date);
	return `${year}-${((month < 10) ? ('0'+month) : month)}-${date}`;
};


const whatDayIsIt = ( day ) => {
	const week = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
	return week[day];
};


// // 달의 마지막 날짜
const getEndOfMonth = ( year, month ) => {

	const leap = (new Date(year, 2, 0).getDate() === 29 ? 29 : 28);

	const lastDatesOfMonth = [31, leap, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
	const lastDateOfThisMonth = lastDatesOfMonth[month];

	return lastDateOfThisMonth;
};


const dayKnot = ( year, month, lastDate ) => {

	if (lastDate === undefined) return;

	const result = {
		first: '',
		last: ''
	};

	result.first = new Date(year, month, 1).getDay();
	result.last = new Date(year, month, lastDate).getDay();

	return result;
};


const setDateInfo = ( dateObj, isToday ) => {
	// console.log('setDateInfo', isToday);
	const year = dateObj.getFullYear();
	const month = dateObj.getMonth();
	const date = dateObj.getDate();
	const day = dateObj.getDay();

	const lastDate = getEndOfMonth(year, month);
	const dayday = dayKnot(year, month, lastDate);

	const today = (isToday === 'today') ? true : false;

	return {
		isToday: today,
		year: year,
		month: month,
		date: date,
		lastDate: lastDate,
		firstDay: dayday.first,
		day: whatDayIsIt(day),
		lastDay: dayday.last,
	};
};