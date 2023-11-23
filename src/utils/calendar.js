import { toString } from "./converters";

const result = {
	days: [],
	modified: []
}

const buttonText = {
	prev: '<',
	next: '>',
	today: '오늘'
};

const setTemp = ( data ) => {
	console.log('dddddd', data);
	return data;
}


// Basic Settings
const dateToString = ( year, month, date ) => {
	console.log('dateToString', year, month, date);
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
	console.log('setDateInfo', isToday);
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


const getDates = ( date ) => {
	if (date === undefined) return;
	console.log('getDates', date);
	// if (date === '') {
	// 	const now = new Date();
	// 	return setDateInfo(now, 'today');
	// } else {
	// 	const now = new Date(date);
	// 	return setDateInfo(now, '');
	// }

	if (!(date.length === 0)) {
		const now = new Date(date);
		return setDateInfo(now, '');
	} else {
		const now = new Date();
		return setDateInfo(now, 'today');
	}

	// const dateObj = (date === '' ?  : new Date(date));
	// console.log('dd', date);
	// if (date === '') return setDateInfo(dateObj, 'today');
	// return 
};




// // Interaction function
// const goToLastMonth = () => {
// 	// const data = [...temp];
// 	const data = setTemp();
// 	if (data[1] === 0) {
// 		data[1] = 11;
// 		data[0] = data[0] - 1;
// 		setTemp(() => data);
// 	} else {
// 		data[1] = data[1] - 1;
// 		setTemp(() => data);
// 	}
// };


// const goToNextMonth = () => {
// 	// const data = [...temp];
// 	const data = setTemp();
// 	if (data[1] === 11) {
// 		data[1] = 0;
// 		data[0] = data[0] + 1;
// 		setTemp(() => data);
// 	} else {
// 		data[1] = data[1] + 1;
// 		setTemp(() => data);
// 	}
// };


// 날짜 셋팅
const setDays = ( processedDateObj ) => {
	console.log('setDays', processedDateObj);
	// const currentDate = [...arry];

	const startDay = processedDateObj.firstDay;
	const lastDay = processedDateObj.lastDay;
	const endDate = processedDateObj.lastDate;

	// const point = processedDateObj.string;

	let i = 0;
	let min = (startDay - 1) * -1;

	const weekdays = 7;
	const last = weekdays - lastDay;
	const days = [];
	const spaces = endDate + last;
	console.log('1a', startDay, lastDay, endDate, min, last, spaces);
	// new Date(2022, 10, 0)
	// new Date(2022, 10, -1)
	// new Date(2022, 10, -2)

	while (min < spaces) {
		let day = new Date(processedDateObj.year, processedDateObj.month, min);
		let key = (new Date().getMilliseconds()) + min;

		let isToday = dateToString(processedDateObj.year, processedDateObj.month, min);

		// days[i] = {id: key, year: day.getFullYear(), month: day.getMonth(), date: day.getDate(), day: day.getDay(), onToday: (point === isToday ? true : false)};
		result.days[i] = {id: key, year: day.getFullYear(), month: day.getMonth(), date: day.getDate(), day: day.getDay(), onToday: (isToday ? true : false)};
		min++;
		i++;
	}
	return result.days;
};


const dateCaculator = (val, today) => {
	let requestDate = '';
	const calculated = {
		nowDates: '',
		days: '',
	};

	switch (val) {
		case buttonText.today:
			console.log('1');
			requestDate = dateToString(today.year, today.month, today.date);
			calculated.days = setDays(requestDate);
			console.log('nana?', calculated);
			return calculated.days;

		case buttonText.prev:
			console.log('mamamam', today.month);
			requestDate = dateToString(today.year, today.month, today.date);

			console.log('???', getDates(requestDate), getDates('2023-10-21'));
			// calculated.nowDates = new Date(today.year-1, today.month-2, today.date);
			calculated.nowDates = getDates(requestDate);
			calculated.days = setDays(calculated.nowDates);
			console.log('2', (buttonText.prev), calculated);
			return;

		case buttonText.next:
			console.log('3');
			return;

		default:
			console.log('0');
			calculated.days = setDays(today);
			console.log('nana?', calculated);
			return calculated.days;
	}
}

const today = getDates('');
const todays = setDays(today);
console.log('haha?', todays);



const flipOverCalendar = (event) => {
	const val = event.target.innerText;
	// const today = getDates('');
	

	dateCaculator(val, today);
	// switch (val) {
	// 	case buttonText.today:
	// 		console.log('1');
	// 		requestDate = dateToString(today.year, today.month, today.date);
	// 		calculated.days = setDays(requestDate);
	// 		console.log('nana?', calculated);
	// 		event.stopPropagation();
	// 		return calculated.days;
	// 	case buttonText.prev:
	// 		console.log('mamamam', today.month);
	// 		requestDate = dateToString(today.year, today.month-1, today.date);
	// 		// calculated.nowDates = new Date(today.year-1, today.month-2, today.date);
	// 		calculated.nowDates = getDates(requestDate);
	// 		calculated.days = setDays(calculated.nowDates);
	// 		console.log('2', (buttonText.prev), calculated);
	// 		event.stopPropagation();
	// 		return;
	// 	case buttonText.next:
	// 		console.log('3');
	// 		event.stopPropagation();
	// 		return;
	// 	default:
	// 		console.log('0');
	// 		calculated.days = setDays(today);
	// 		console.log('nana?', calculated);
	// 		event.stopPropagation();
	// 		return calculated.days;
	// }
};
// const calendarProps = {
// 	year,
// 	month,
// 	week,
// 	calendar,
// 	buttonText,
// 	flipOver,
// }

export const vanillaCalendar = () => {
	// const test = '2020-02-29';
	// const testDates = getDates(test);

	// const days = setDays(testDates);
	
  // console.log('ha?', nowDates);
	// console.log('ha?', testDates);
	
  return (
		<>
			<button onClick={flipOverCalendar}>{buttonText.prev}</button>
			<button onClick={flipOverCalendar}>{buttonText.today}</button>
			<button onClick={flipOverCalendar}>{buttonText.next}</button>
		</>
	);
}





{/* <>
	<Container main>

		<Title right pseudoBefore>
			<Year>{year}</Year>
		</Title>

		<Wrapper>
			<Container left>
				<Month>{(month < 10 ? ('0' + month) : month)}</Month>
				<ButtonContainer>
					<Button onClick={flipOver}>{buttonText.prev}</Button>
					<Button onClick={flipOver}>{buttonText.today}</Button>
					<Button onClick={flipOver}>{buttonText.next}</Button>
				</ButtonContainer>
			</Container>

			<Container right>
				<GridTable>
					{week.map((item, index) => (<TableCellText day key={index}>{item}</TableCellText>))}
					{calendar.map((item) => { 
						if (item.month < month - 1 || item.month > month - 1) {
							return (<TableCell over key={item.id}>
								{item.day === 0 ? <TableCellText sun>{item.date}</TableCellText> : (item.day === 6 ? <TableCellText sat>{item.date}</TableCellText> : (<TableCellText>{item.date}</TableCellText>))}
							</TableCell>)
						} else if (item.onToday) {
							return (<TableCell point key={item.id}>
								{item.day === 0 ? <TableCellText sun>{item.date}</TableCellText> : (item.day === 6 ? <TableCellText sat>{item.date}</TableCellText> : (<TableCellText>{item.date}</TableCellText>))}
							</TableCell>)
						} else {
							return (<TableCell key={item.id}>
								{item.day === 0 ? <TableCellText sun>{item.date}</TableCellText> : (item.day === 6 ? <TableCellText sat>{item.date}</TableCellText> : (<TableCellText>{item.date}</TableCellText>))}
							</TableCell>)
						}
					})}
				</GridTable>
			</Container>
		</Wrapper>

	</Container>
</> */}