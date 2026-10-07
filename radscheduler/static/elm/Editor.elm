port module Editor exposing (main)

{-| The roster editor: a grid of registrars by dates for three weeks, with shifts and leave in each cell.

The data comes from /api/editor/roster in one request. Menus for adding and changing shifts and leave are
drawn only while open, so the grid stays light however many cells it has.

-}

import Browser
import Browser.Events
import Dict exposing (Dict)
import Editor.Api as Api exposing (Choice, Leave, Published, Registrar, Roster, Shift)
import Html exposing (..)
import Html.Attributes exposing (..)
import Html.Events exposing (on, onCheck, onClick, targetValue)
import Http
import Json.Decode as Decode
import Json.Encode as Encode
import Set exposing (Set)


port pushUrl : String -> Cmd msg


port onUrlChange : (String -> msg) -> Sub msg


main : Program Decode.Value Model Msg
main =
    Browser.element
        { init = init
        , update = update
        , view = view
        , subscriptions = subscriptions
        }



-- MODEL


type alias Flags =
    { csrfToken : String
    , week : String
    , editorUrl : String
    , shiftTypes : List Choice
    , leaveTypes : List Choice
    }


type alias Model =
    { flags : Flags
    , week : String
    , roster : Maybe Roster
    , loading : Bool
    , error : Maybe String
    , hiddenShiftTypes : Set String
    , hiddenLeaveTypes : Set String
    , menu : Maybe Menu
    , settings : Maybe Published
    }


type Menu
    = AddShiftMenu Int String
    | ShiftMenu Int
    | ConfirmDeleteMenu Int
    | LeaveMenu Int


flagsDecoder : Decode.Decoder Flags
flagsDecoder =
    Decode.map5 Flags
        (Decode.field "csrfToken" Decode.string)
        (Decode.field "week" Decode.string)
        (Decode.field "editorUrl" Decode.string)
        (Decode.field "shiftTypes" (Decode.list Api.choiceDecoder))
        (Decode.field "leaveTypes" (Decode.list Api.choiceDecoder))


init : Decode.Value -> ( Model, Cmd Msg )
init value =
    case Decode.decodeValue flagsDecoder value of
        Ok flags ->
            ( { flags = flags
              , week = flags.week
              , roster = Nothing
              , loading = True
              , error = Nothing
              , hiddenShiftTypes = Set.empty
              , hiddenLeaveTypes = Set.empty
              , menu = Nothing
              , settings = Nothing
              }
            , Api.getRoster flags.week (GotRoster flags.week)
            )

        Err err ->
            ( { flags = { csrfToken = "", week = "", editorUrl = "", shiftTypes = [], leaveTypes = [] }
              , week = ""
              , roster = Nothing
              , loading = False
              , error = Just ("The editor couldn't start: " ++ Decode.errorToString err)
              , hiddenShiftTypes = Set.empty
              , hiddenLeaveTypes = Set.empty
              , menu = Nothing
              , settings = Nothing
              }
            , Cmd.none
            )



-- UPDATE


type Msg
    = GotRoster String (Result Http.Error Roster)
    | GoToWeek String
    | UrlChanged String
    | ToggleShiftType String Bool
    | ToggleLeaveType String Bool
    | OpenMenu Menu
    | CloseMenu
    | AddShift Int String String
    | ChangeShiftType Int String
    | SetExtraDuty Int Bool
    | DeleteShift Int
    | GotShift (Result Http.Error Shift)
    | ShiftDeleted Int (Result Http.Error ())
    | ChangeLeave Int String Encode.Value
    | GotLeave (Result Http.Error Leave)
    | OpenSettings
    | SetPublishStart String
    | SetPublishEnd String
    | SaveSettings
    | GotPublished (Result Http.Error Published)
    | CloseSettings
    | DismissError


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotRoster week result ->
            if week /= model.week then
                -- A newer week was asked for while this one loaded.
                ( model, Cmd.none )

            else
                case result of
                    Ok roster ->
                        ( { model | roster = Just roster, loading = False }, Cmd.none )

                    Err err ->
                        ( { model | loading = False, error = Just (Api.httpErrorMessage err) }, Cmd.none )

        GoToWeek week ->
            if String.isEmpty week || week == model.week then
                ( model, Cmd.none )

            else
                load week model
                    |> Tuple.mapSecond (\cmd -> Cmd.batch [ cmd, pushUrl (model.flags.editorUrl ++ week ++ "/") ])

        UrlChanged path ->
            case weekFromPath path of
                Just week ->
                    if week == model.week then
                        ( model, Cmd.none )

                    else
                        load week model

                Nothing ->
                    ( model, Cmd.none )

        ToggleShiftType value shown ->
            ( { model | hiddenShiftTypes = toggle value shown model.hiddenShiftTypes }, Cmd.none )

        ToggleLeaveType value shown ->
            ( { model | hiddenLeaveTypes = toggle value shown model.hiddenLeaveTypes }, Cmd.none )

        OpenMenu menu ->
            ( { model | menu = Just menu }, Cmd.none )

        CloseMenu ->
            ( { model | menu = Nothing }, Cmd.none )

        AddShift registrar date type_ ->
            ( { model | menu = Nothing }
            , Api.addShift model.flags.csrfToken { date = date, type_ = type_, registrar = registrar } GotShift
            )

        ChangeShiftType shiftId type_ ->
            ( { model | menu = Nothing }
            , Api.changeShift model.flags.csrfToken shiftId [ ( "type", Encode.string type_ ) ] GotShift
            )

        SetExtraDuty shiftId extraDuty ->
            ( { model | menu = Nothing }
            , Api.changeShift model.flags.csrfToken shiftId [ ( "extra_duty", Encode.bool extraDuty ) ] GotShift
            )

        DeleteShift shiftId ->
            ( { model | menu = Nothing }, Api.deleteShift model.flags.csrfToken shiftId (ShiftDeleted shiftId) )

        GotShift (Ok shift) ->
            ( updateRoster (\r -> { r | shifts = upsert shift r.shifts }) model, Cmd.none )

        ShiftDeleted shiftId (Ok ()) ->
            ( updateRoster (\r -> { r | shifts = List.filter (\s -> s.id /= shiftId) r.shifts }) model, Cmd.none )

        ChangeLeave leaveId field value ->
            ( model, Api.changeLeave model.flags.csrfToken leaveId [ ( field, value ) ] GotLeave )

        GotLeave (Ok leave) ->
            ( updateRoster (\r -> { r | leaves = upsert leave r.leaves }) model, Cmd.none )

        GotShift (Err err) ->
            ( saveFailed err model, Cmd.none )

        ShiftDeleted _ (Err err) ->
            ( saveFailed err model, Cmd.none )

        GotLeave (Err err) ->
            ( saveFailed err model, Cmd.none )

        OpenSettings ->
            let
                draft =
                    model.roster
                        |> Maybe.andThen .published
                        |> Maybe.withDefault { start = model.week, end = model.week }
            in
            ( { model | settings = Just draft, menu = Nothing }, Cmd.none )

        SetPublishStart start ->
            ( { model | settings = Maybe.map (\d -> { d | start = start }) model.settings }, Cmd.none )

        SetPublishEnd end ->
            ( { model | settings = Maybe.map (\d -> { d | end = end }) model.settings }, Cmd.none )

        SaveSettings ->
            case model.settings of
                Just draft ->
                    if validRange draft then
                        ( model, Api.setPublished model.flags.csrfToken draft GotPublished )

                    else
                        ( model, Cmd.none )

                Nothing ->
                    ( model, Cmd.none )

        GotPublished (Ok published) ->
            ( updateRoster (\r -> { r | published = Just published }) { model | settings = Nothing }, Cmd.none )

        GotPublished (Err err) ->
            ( saveFailed err model, Cmd.none )

        CloseSettings ->
            ( { model | settings = Nothing }, Cmd.none )

        DismissError ->
            ( { model | error = Nothing }, Cmd.none )


validRange : Published -> Bool
validRange range =
    -- ISO dates sort as strings.
    not (String.isEmpty range.start) && not (String.isEmpty range.end) && range.start <= range.end


load : String -> Model -> ( Model, Cmd Msg )
load week model =
    ( { model | week = week, loading = True, menu = Nothing }, Api.getRoster week (GotRoster week) )


saveFailed : Http.Error -> Model -> Model
saveFailed err model =
    { model | error = Just ("Couldn't save the change. " ++ Api.httpErrorMessage err) }


updateRoster : (Roster -> Roster) -> Model -> Model
updateRoster f model =
    { model | roster = Maybe.map f model.roster }


upsert : { a | id : Int } -> List { a | id : Int } -> List { a | id : Int }
upsert item items =
    if List.any (\i -> i.id == item.id) items then
        List.map
            (\i ->
                if i.id == item.id then
                    item

                else
                    i
            )
            items

    else
        items ++ [ item ]


toggle : comparable -> Bool -> Set comparable -> Set comparable
toggle value shown hidden =
    if shown then
        Set.remove value hidden

    else
        Set.insert value hidden


{-| The week is the last part of the editor's URL, e.g. /roster/editor/next/2026-10-12/.
-}
weekFromPath : String -> Maybe String
weekFromPath path =
    path
        |> String.split "/"
        |> List.filter (not << String.isEmpty)
        |> List.reverse
        |> List.head
        |> Maybe.andThen
            (\part ->
                if String.length part == 10 then
                    Just part

                else
                    Nothing
            )



-- SUBSCRIPTIONS


subscriptions : Model -> Sub Msg
subscriptions model =
    Sub.batch
        [ onUrlChange UrlChanged
        , case ( model.settings, model.menu ) of
            ( Just _, _ ) ->
                onEscape CloseSettings

            ( Nothing, Just _ ) ->
                onEscape CloseMenu

            ( Nothing, Nothing ) ->
                Sub.none
        ]


onEscape : Msg -> Sub Msg
onEscape msg =
    Browser.Events.onKeyDown
        (Decode.field "key" Decode.string
            |> Decode.andThen
                (\key ->
                    if key == "Escape" then
                        Decode.succeed msg

                    else
                        Decode.fail key
                )
        )



-- VIEW


view : Model -> Html Msg
view model =
    div [ class "container-fluid" ]
        [ div [ class "d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2" ]
            [ h1 [ class "mb-0" ] [ text "Roster Editor" ]
            , viewPublished model.roster
            ]
        , viewMenuBar model
        , viewError model.error
        , viewSettings model.settings
        , case model.roster of
            Just roster ->
                viewTable model roster

            Nothing ->
                if model.loading then
                    p [ class "text-body-secondary" ] [ text "Loading the roster…" ]

                else
                    text ""
        ]


viewPublished : Maybe Roster -> Html Msg
viewPublished roster =
    case roster |> Maybe.andThen .published of
        Just published ->
            div [ class "d-flex align-items-center gap-2 text-body-secondary" ]
                [ i [ class "bi bi-calendar-range", attribute "aria-hidden" "true" ] []
                , span []
                    [ text "Published: "
                    , strong [] [ text (longDate published.start) ]
                    , text " – "
                    , strong [] [ text (longDate published.end) ]
                    ]
                ]

        Nothing ->
            text ""


viewError : Maybe String -> Html Msg
viewError error =
    case error of
        Just message ->
            div [ class "alert alert-danger d-flex justify-content-between align-items-center", attribute "role" "alert" ]
                [ text message
                , button [ type_ "button", class "btn-close", attribute "aria-label" "Dismiss", onClick DismissError ] []
                ]

        Nothing ->
            text ""


viewMenuBar : Model -> Html Msg
viewMenuBar model =
    let
        navigation =
            case model.roster of
                Just roster ->
                    [ div [ class "input-group flex-nowrap w-auto" ]
                        [ button [ type_ "button", class "btn btn-outline-secondary", title "Previous week", attribute "aria-label" "Previous week", onClick (GoToWeek roster.prev) ]
                            [ i [ class "bi bi-chevron-left" ] [] ]
                        , input
                            [ type_ "date"
                            , class "form-control text-center"
                            , style "min-width" "130px"
                            , style "max-width" "160px"
                            , value model.week
                            , attribute "aria-label" "Week in focus"
                            , on "change" (Decode.map GoToWeek targetValue)
                            ]
                            []
                        , button [ type_ "button", class "btn btn-outline-secondary", title "Next week", attribute "aria-label" "Next week", onClick (GoToWeek roster.next) ]
                            [ i [ class "bi bi-chevron-right" ] [] ]
                        ]
                    , button [ type_ "button", class "btn btn-outline-primary", onClick (GoToWeek roster.today) ] [ text "Today" ]
                    ]

                Nothing ->
                    []
    in
    div [ id "menu-bar", class "d-flex flex-column flex-xl-row flex-wrap flex-xl-nowrap align-items-center gap-3 p-2 mx-0 my-2 border border-2 shadow-sm bg-light rounded" ]
        [ div [ class "d-flex align-items-center gap-2" ] navigation
        , div [ class "d-flex flex-column gap-1 flex-grow-1" ]
            [ viewFilter "Shifts" "shift-type" model.flags.shiftTypes model.hiddenShiftTypes ToggleShiftType
            , viewFilter "Leave" "leave-type" model.flags.leaveTypes model.hiddenLeaveTypes ToggleLeaveType
            ]
        , if model.loading then
            span [ class "spinner-border spinner-border-sm text-secondary", attribute "role" "status" ]
                [ span [ class "visually-hidden" ] [ text "Loading" ] ]

          else
            text ""
        , button [ type_ "button", class "btn btn-secondary text-nowrap", onClick OpenSettings ]
            [ i [ class "bi bi-gear-fill me-1", attribute "aria-hidden" "true" ] [], text "Settings" ]
        ]


viewSettings : Maybe Published -> Html Msg
viewSettings settings =
    case settings of
        Just draft ->
            let
                field fieldId labelText current toMsg =
                    div [ class "mb-3" ]
                        [ label [ class "form-label", for fieldId ] [ text labelText ]
                        , input [ type_ "date", class "form-control", id fieldId, value current, Html.Events.onInput toMsg ] []
                        ]
            in
            div []
                [ div [ class "modal d-block", attribute "role" "dialog", attribute "aria-modal" "true", attribute "aria-labelledby" "settings-title" ]
                    [ div [ class "modal-dialog" ]
                        [ Html.form [ class "modal-content", Html.Events.onSubmit SaveSettings ]
                            [ div [ class "modal-header" ]
                                [ h2 [ class "modal-title fs-5", id "settings-title" ] [ text "Published dates" ]
                                , button [ type_ "button", class "btn-close", attribute "aria-label" "Close", onClick CloseSettings ] []
                                ]
                            , div [ class "modal-body" ]
                                [ p [ class "text-body-secondary small" ] [ text "Registrars only see shifts and leave between these dates." ]
                                , field "publish-start" "Start" draft.start SetPublishStart
                                , field "publish-end" "End" draft.end SetPublishEnd
                                , if validRange draft then
                                    text ""

                                  else
                                    p [ class "text-danger small mb-0" ] [ text "The start must be on or before the end." ]
                                ]
                            , div [ class "modal-footer" ]
                                [ button [ type_ "button", class "btn btn-outline-secondary", onClick CloseSettings ] [ text "Cancel" ]
                                , button [ type_ "submit", class "btn btn-primary", disabled (not (validRange draft)) ] [ text "Save" ]
                                ]
                            ]
                        ]
                    ]
                , div [ class "modal-backdrop show" ] []
                ]

        Nothing ->
            text ""


viewFilter : String -> String -> List Choice -> Set String -> (String -> Bool -> Msg) -> Html Msg
viewFilter legend idPrefix choices hidden toMsg =
    fieldset [ class "d-flex flex-wrap align-items-center gap-2" ]
        (Html.legend [ class "col-form-label col-form-label-sm p-0 me-1 float-none w-auto" ] [ text legend ]
            :: List.map
                (\choice ->
                    let
                        inputId =
                            idPrefix ++ "-" ++ choice.value
                    in
                    div [ class "form-check form-check-inline m-0" ]
                        [ input
                            [ type_ "checkbox"
                            , class "form-check-input"
                            , id inputId
                            , checked (not (Set.member choice.value hidden))
                            , onCheck (toMsg choice.value)
                            ]
                            []
                        , label [ class "form-check-label small", for inputId ] [ text choice.label ]
                        ]
                )
                choices
        )


viewTable : Model -> Roster -> Html Msg
viewTable model roster =
    let
        holidays =
            Dict.fromList (List.map (\h -> ( h.date, h.name )) roster.holidays)

        shifts =
            roster.shifts
                |> List.filter (\s -> not (Set.member s.type_ model.hiddenShiftTypes))
                |> groupBy (\s -> ( s.registrar, s.date ))

        leaves =
            roster.leaves
                |> List.filter (\l -> not (Set.member l.type_ model.hiddenLeaveTypes))
                |> groupBy (\l -> ( l.registrar, l.date ))

        day =
            { today = roster.today, holidays = holidays }
    in
    div [ id "roster-editor", class "table-responsive overflow-y-scroll", style "height" "80vh", attribute "aria-busy" (boolString model.loading) ]
        [ table [ class "table table-hover table-bordered" ]
            [ thead []
                [ tr [ class "text-center table-light" ]
                    (th [ scope "col", style "width" "100px" ] []
                        :: List.map (viewDateHeader day) roster.dates
                    )
                ]
            , tbody [ class "text-center" ]
                (List.map (viewRow model day roster.dates shifts leaves) roster.registrars)
            , tfoot []
                [ tr [ class "text-center table-light" ]
                    (th [ scope "row", class "text-secondary text-start small" ] [ text "Leave" ]
                        :: List.map (viewLeaveCount roster.leaves) roster.dates
                    )
                ]
            ]
        ]


type alias Day =
    { today : String
    , holidays : Dict String String
    }


dayClass : Day -> String -> String
dayClass day date =
    if date == day.today then
        "table-active"

    else if Dict.member date day.holidays then
        "table-info"

    else if isWeekend date then
        "table-warning"

    else
        ""


viewDateHeader : Day -> String -> Html Msg
viewDateHeader day date =
    th [ scope "col", class (dayClass day date), style "min-width" "150px" ]
        [ div [] [ text date ]
        , div []
            (text (weekdayName date)
                :: (case Dict.get date day.holidays of
                        Just name ->
                            [ text " ", span [ title name ] [ text "🎉" ], span [ class "visually-hidden" ] [ text name ] ]

                        Nothing ->
                            []
                   )
            )
        ]


viewRow : Model -> Day -> List String -> Dict ( Int, String ) (List Shift) -> Dict ( Int, String ) (List Leave) -> Registrar -> Html Msg
viewRow model day dates shifts leaves registrar =
    tr []
        (th [ scope "row", class "text-start align-middle border", style "height" "35px" ] [ text registrar.username ]
            :: List.map
                (\date ->
                    viewCell model
                        day
                        registrar
                        date
                        (Dict.get ( registrar.id, date ) shifts |> Maybe.withDefault [])
                        (Dict.get ( registrar.id, date ) leaves |> Maybe.withDefault [])
                )
                dates
        )


viewCell : Model -> Day -> Registrar -> String -> List Shift -> List Leave -> Html Msg
viewCell model day registrar date shifts leaves =
    td
        [ id ("cell-" ++ date ++ "-" ++ String.fromInt registrar.id)
        , class ("font-monospace px-0 align-middle " ++ dayClass day date)
        ]
        [ div [ class "d-flex flex-column align-items-start justify-content-start gap-1 px-1 m-0" ]
            (List.map (viewShift model) shifts
                ++ List.map (viewLeave model) leaves
                ++ [ viewAddShift model registrar date ]
            )
        ]


viewShift : Model -> Shift -> Html Msg
viewShift model shift =
    let
        open =
            model.menu == Just (ShiftMenu shift.id) || model.menu == Just (ConfirmDeleteMenu shift.id)
    in
    div [ class "btn-group position-relative w-100" ]
        [ button
            [ type_ "button"
            , class ("btn btn-sm dropdown-toggle shadow py-1 w-100 " ++ shiftClass shift.type_)
            , attribute "aria-expanded" (boolString open)
            , attribute "aria-haspopup" "menu"
            , onClick (OpenMenu (ShiftMenu shift.id))
            ]
            (text shift.type_
                :: (if shift.extraDuty then
                        [ text " ", i [ class "bi bi-coin", title "Extra duty" ] [], span [ class "visually-hidden" ] [ text "Extra duty" ] ]

                    else
                        []
                   )
            )
        , if model.menu == Just (ShiftMenu shift.id) then
            viewMenu
                [ h6 [ class "dropdown-header" ] [ text "Change shift type" ]
                , div [] (List.map (shiftTypeItem shift) model.flags.shiftTypes)
                , div [ class "btn-group btn-group-sm w-100 mt-2", attribute "role" "group" ]
                    [ button
                        [ type_ "button"
                        , class
                            (if shift.extraDuty then
                                "btn btn-success"

                             else
                                "btn btn-outline-success"
                            )
                        , attribute "aria-pressed" (boolString shift.extraDuty)
                        , onClick (SetExtraDuty shift.id (not shift.extraDuty))
                        ]
                        [ i [ class "bi bi-coin px-1" ] [], text "Extra" ]
                    , button [ type_ "button", class "btn btn-outline-danger", onClick (OpenMenu (ConfirmDeleteMenu shift.id)) ]
                        [ i [ class "bi bi-trash3 px-1" ] [], text "Delete" ]
                    ]
                ]

          else if model.menu == Just (ConfirmDeleteMenu shift.id) then
            viewMenu
                [ p [ class "small mb-2" ] [ text ("Delete this " ++ shift.type_ ++ " shift?") ]
                , div [ class "d-flex gap-2" ]
                    [ button [ type_ "button", class "btn btn-sm btn-danger", onClick (DeleteShift shift.id) ] [ text "Delete" ]
                    , button [ type_ "button", class "btn btn-sm btn-outline-secondary", onClick CloseMenu ] [ text "Cancel" ]
                    ]
                ]

          else
            text ""
        ]


shiftTypeItem : Shift -> Choice -> Html Msg
shiftTypeItem shift choice =
    button
        [ type_ "button"
        , classList [ ( "dropdown-item", True ), ( "active", choice.value == shift.type_ ) ]
        , onClick (ChangeShiftType shift.id choice.value)
        ]
        [ text choice.label ]


viewAddShift : Model -> Registrar -> String -> Html Msg
viewAddShift model registrar date =
    let
        open =
            model.menu == Just (AddShiftMenu registrar.id date)
    in
    div [ class "btn-group position-relative" ]
        [ button
            [ type_ "button"
            , class "btn btn-sm btn-outline-primary dropdown-toggle shadow"
            , attribute "aria-label" ("Add a shift for " ++ registrar.username ++ " on " ++ date)
            , attribute "aria-expanded" (boolString open)
            , attribute "aria-haspopup" "menu"
            , onClick (OpenMenu (AddShiftMenu registrar.id date))
            ]
            []
        , if open then
            viewMenu
                (div [ class "form-text mb-2" ] [ text "New shift:" ]
                    :: List.map
                        (\choice ->
                            button [ type_ "button", class "dropdown-item", onClick (AddShift registrar.id date choice.value) ]
                                [ text choice.label ]
                        )
                        model.flags.shiftTypes
                )

          else
            text ""
        ]


viewLeave : Model -> Leave -> Html Msg
viewLeave model leave =
    let
        open =
            model.menu == Just (LeaveMenu leave.id)

        state =
            leaveState leave
    in
    div [ class "btn-group position-relative w-100" ]
        [ button
            [ type_ "button"
            , class ("btn btn-sm dropdown-toggle py-1 w-100 " ++ leaveClass state)
            , attribute "aria-expanded" (boolString open)
            , attribute "aria-haspopup" "menu"
            , title (leaveTitle state leave)
            , onClick (OpenMenu (LeaveMenu leave.id))
            ]
            [ i [ class ("bi me-1 " ++ leaveIcon state), attribute "aria-hidden" "true" ] []
            , text (leaveLabel leave)
            , span [ class "visually-hidden" ] [ text (", " ++ leaveStateName state) ]
            ]
        , if open then
            viewMenu
                [ h6 [ class "dropdown-header" ] [ text "Roster master" ]
                , approvalButtons leave "reg_approved" leave.regApproved
                , h6 [ class "dropdown-header" ] [ text "Director" ]
                , approvalButtons leave "dot_approved" leave.dotApproved
                , div [ class "form-check mt-3" ]
                    [ input
                        [ type_ "checkbox"
                        , class "form-check-input"
                        , id ("leave-" ++ String.fromInt leave.id ++ "-cancelled")
                        , checked leave.cancelled
                        , onCheck (\c -> ChangeLeave leave.id "cancelled" (Encode.bool c))
                        ]
                        []
                    , label [ class "form-check-label", for ("leave-" ++ String.fromInt leave.id ++ "-cancelled") ] [ text "Cancelled" ]
                    ]
                , hr [ class "dropdown-divider" ] []
                , if String.isEmpty leave.comment then
                    text ""

                  else
                    p [ class "small mb-2 text-start" ] [ text leave.comment ]
                , p [ class "small mb-0 text-start" ] [ text ("Created: " ++ shortDateTime leave.created) ]
                , p [ class "small mb-0 text-start" ] [ text ("Last updated: " ++ shortDateTime leave.lastEdited) ]
                ]

          else
            text ""
        ]


approvalButtons : Leave -> String -> Maybe Bool -> Html Msg
approvalButtons leave field current =
    let
        option value icon name style_ =
            button
                [ type_ "button"
                , class
                    ("btn "
                        ++ (if current == value then
                                "btn-" ++ style_

                            else
                                "btn-outline-" ++ style_
                           )
                    )
                , title name
                , attribute "aria-label" name
                , attribute "aria-pressed" (boolString (current == value))
                , disabled leave.cancelled
                , onClick (ChangeLeave leave.id field (encodeMaybeBool value))
                ]
                [ i [ class ("bi " ++ icon) ] [] ]
    in
    div [ class "btn-group btn-group-sm w-100", attribute "role" "group" ]
        [ option (Just True) "bi-check-lg" "Approve" "success"
        , option Nothing "bi-question-lg" "Pending" "secondary"
        , option (Just False) "bi-x-lg" "Decline" "danger"
        ]


{-| An open menu, with a transparent backdrop behind it that closes it when clicked.
-}
viewMenu : List (Html Msg) -> Html Msg
viewMenu content =
    div []
        [ div
            [ style "position" "fixed"
            , style "inset" "0"
            , style "z-index" "1040"
            , onClick CloseMenu
            ]
            []
        , div
            [ class "dropdown-menu show p-2 shadow"
            , attribute "role" "menu"
            , style "position" "absolute"
            , style "top" "100%"
            , style "left" "0"
            , style "z-index" "1050"
            , style "min-width" "200px"
            ]
            content
        ]


viewLeaveCount : List Leave -> String -> Html Msg
viewLeaveCount leaves date =
    if isWeekend date then
        th [ scope "col" ] []

    else
        let
            onDay =
                List.filter (\l -> l.date == date && not l.cancelled) leaves

            count state =
                List.length (List.filter (\l -> leaveState l == state) onDay)
        in
        th [ scope "col", class "small fw-normal" ]
            [ span [ class "text-success", title "Approved" ] [ text (String.fromInt (count Approved)) ]
            , text " / "
            , span [ class "text-warning-emphasis", title "Pending" ] [ text (String.fromInt (count Pending + count PartlyApproved)) ]
            , text " / "
            , span [ title "Total" ] [ text (String.fromInt (List.length onDay)) ]
            ]



-- LEAVE STATE


type LeaveState
    = Cancelled
    | Declined
    | Approved
    | PartlyApproved
    | Pending


leaveState : Leave -> LeaveState
leaveState leave =
    if leave.cancelled then
        Cancelled

    else if leave.regApproved == Just False || leave.dotApproved == Just False then
        Declined

    else if leave.regApproved == Just True && leave.dotApproved == Just True then
        Approved

    else if leave.regApproved == Just True || leave.dotApproved == Just True then
        PartlyApproved

    else
        Pending


leaveClass : LeaveState -> String
leaveClass state =
    case state of
        Cancelled ->
            "text-decoration-line-through btn-outline-secondary"

        Declined ->
            "text-decoration-line-through btn-outline-danger"

        Approved ->
            "btn-outline-success"

        PartlyApproved ->
            "btn-outline-warning shadow"

        Pending ->
            "btn-outline-secondary"


leaveIcon : LeaveState -> String
leaveIcon state =
    case state of
        Cancelled ->
            "bi-slash-circle"

        Declined ->
            "bi-x-lg"

        Approved ->
            "bi-check-lg"

        PartlyApproved ->
            "bi-hourglass-split"

        Pending ->
            "bi-question-lg"


leaveStateName : LeaveState -> String
leaveStateName state =
    case state of
        Cancelled ->
            "cancelled"

        Declined ->
            "declined"

        Approved ->
            "approved"

        PartlyApproved ->
            "partly approved"

        Pending ->
            "pending"


leaveLabel : Leave -> String
leaveLabel leave =
    if leave.portion == "ALL" then
        leave.type_

    else
        leave.type_ ++ " " ++ leave.portion


leaveTitle : LeaveState -> Leave -> String
leaveTitle state leave =
    String.join " — " (List.filter (not << String.isEmpty) [ leaveStateName state, leave.comment ])



-- HELPERS


shiftClass : String -> String
shiftClass shiftType =
    case shiftType of
        "LONG" ->
            "btn-danger"

        "SWING" ->
            "btn-danger"

        "HELP" ->
            "btn-info"

        "NIGHT" ->
            "btn-dark"

        _ ->
            "btn-warning"


groupBy : (a -> comparable) -> List a -> Dict comparable (List a)
groupBy key items =
    List.foldr
        (\item acc -> Dict.update (key item) (\existing -> Just (item :: Maybe.withDefault [] existing)) acc)
        Dict.empty
        items


encodeMaybeBool : Maybe Bool -> Encode.Value
encodeMaybeBool value =
    Maybe.map Encode.bool value |> Maybe.withDefault Encode.null


boolString : Bool -> String
boolString b =
    if b then
        "true"

    else
        "false"


{-| Day of the week for an ISO date, 0 = Monday (Sakamoto's method).
-}
weekday : String -> Int
weekday date =
    case List.map String.toInt (String.split "-" date) of
        [ Just y, Just m, Just d ] ->
            let
                offsets =
                    [ 0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4 ]

                year =
                    if m < 3 then
                        y - 1

                    else
                        y

                offset =
                    List.drop (m - 1) offsets |> List.head |> Maybe.withDefault 0

                sundayFirst =
                    modBy 7 (year + year // 4 - year // 100 + year // 400 + offset + d)
            in
            modBy 7 (sundayFirst + 6)

        _ ->
            0


isWeekend : String -> Bool
isWeekend date =
    weekday date >= 5


weekdayName : String -> String
weekdayName date =
    [ "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun" ]
        |> List.drop (weekday date)
        |> List.head
        |> Maybe.withDefault ""


longDate : String -> String
longDate date =
    case String.split "-" date of
        [ y, m, d ] ->
            let
                month =
                    [ "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" ]
                        |> List.drop ((String.toInt m |> Maybe.withDefault 1) - 1)
                        |> List.head
                        |> Maybe.withDefault m
            in
            month ++ " " ++ String.fromInt (String.toInt d |> Maybe.withDefault 0) ++ ", " ++ y

        _ ->
            date


{-| "2026-10-07T16:21:05.123+13:00" -> "2026-10-07 16:21"
-}
shortDateTime : String -> String
shortDateTime value =
    String.left 16 value |> String.replace "T" " "
