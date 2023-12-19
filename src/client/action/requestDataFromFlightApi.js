// import getTestData from '../components/data/api_get_test_data.json';

export const requestDataFromFlightApi = async ( url, port, line ) => {
  // console.info('call api function', url, port, line);
	const SERVICE_KEY = process.env.REACT_APP_INCHEON_INT_AIRPORT_WEATHER_INFO_API_KEY_A;
	
	const ARRIVAL_URL = `B551177/StatusOfPassengerWorldWeatherInfo/getPassengerArrivalsWorldWeather`;
	const DEPARTURE_URL = `B551177/StatusOfPassengerWorldWeatherInfo/getPassengerDeparturesWorldWeather`;
	
	let URL = '';
	const airport = (port === undefined) ? '' : port;
	const airline = (line === undefined) ? '' : line;

	if (url === 'ARRIVAL_URL') {
		URL = ARRIVAL_URL;
	}
	if (url === 'DEPARTURE_URL') {
		URL = DEPARTURE_URL;
	}
	
	const params = {
		'serviceKey': `${SERVICE_KEY}`,
		'numOfRows': '', 
		'pageNo': '1', 
		'from_time': '0000', 
		'to_time': '2400', 
		'airport': `${airport}`,
		'flight_id': '',
		'airline': `${airline}`,
		'lang':'K', 
		'type':'json'
	}

	const queryString = new URLSearchParams(params).toString();

	try {
		const response = await fetch(`/flight-api/${URL}?${queryString}`, {
			method: "GET",
		});

		if (!response.ok) {
			console.error('!! HTTP ERROR TO EXTERNAL API :: status ', response.status);
		}

		const result = await response.json();
		const finalData = result.response.body;

		const items = (finalData.items.length === 0) ? {items: 'nothing'} : finalData;
		let sendItems = items.items;
		return sendItems;
		
	} catch (error) {
		console.error('CAN NOT CONNECT TO EXTERNAL API :: ', error);

		const result = 'nothing';
		return result;

		// local 테스트
		// const forLocal55 = getTestData;
		// return forLocal55;
	}
};
