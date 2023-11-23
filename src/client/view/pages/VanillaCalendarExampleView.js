import { vanillaCalendar } from "../../../utils/calendar"


// 리액트 캘린더와 렌더링 구분
export const VanillaCalendarExampleView = () => {
	const vanillaCalendarPage = vanillaCalendar();

	return (
	<>
		<div>
			<h1>Vanilla JS 캘린더</h1>
			{vanillaCalendarPage}
		</div>
	</>
);
}