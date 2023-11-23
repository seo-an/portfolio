import { HomeCardsView } from "../../view/pages/HomeCardsView";

export const HomeCardsJs = () => {
	const data = [
		{
			id: `calendar`,
			link: `/calendar`,
			text: '캘린더'
		},
		{
			id: `svg-component`,
			link: `/svg-component`,
			text: '컴포넌트형 SVG'
		},
		{
			id: `modal`,
			link: `/modal`,
			text: '모달 팝업'
		},
		{
			id: `window-popup`,
			link: `/window-popup`,
			text: '윈도우 팝업'
		}
	];

	// ,
	// 	{
	// 		id: `date-range-selection`,
	// 		link: `/date-range-selection`,
	// 		text: '일정 계산'
	// 	}

	return (
		<HomeCardsView props = { { data } }/>
	);
}