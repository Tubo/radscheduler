module Editor.Api exposing
    ( Choice
    , Holiday
    , Leave
    , Published
    , Registrar
    , Roster
    , Shift
    , addShift
    , changeLeave
    , changeShift
    , choiceDecoder
    , deleteShift
    , getRoster
    , httpErrorMessage
    )

{-| Types, JSON decoders and requests for the roster editor API at /api/editor/.
-}

import Http
import Json.Decode as Decode exposing (Decoder)
import Json.Encode as Encode


type alias Choice =
    { value : String
    , label : String
    }


type alias Registrar =
    { id : Int
    , username : String
    , year : Maybe Int
    }


type alias Shift =
    { id : Int
    , date : String
    , type_ : String
    , registrar : Int
    , extraDuty : Bool
    }


type alias Leave =
    { id : Int
    , date : String
    , type_ : String
    , portion : String
    , registrar : Int
    , comment : String
    , regApproved : Maybe Bool
    , dotApproved : Maybe Bool
    , cancelled : Bool
    , created : String
    , lastEdited : String
    }


type alias Holiday =
    { date : String
    , name : String
    }


type alias Published =
    { start : String
    , end : String
    }


type alias Roster =
    { week : String
    , prev : String
    , next : String
    , today : String
    , dates : List String
    , registrars : List Registrar
    , shifts : List Shift
    , leaves : List Leave
    , holidays : List Holiday
    , published : Maybe Published
    }



-- DECODERS


andMap : Decoder a -> Decoder (a -> b) -> Decoder b
andMap =
    Decode.map2 (|>)


choiceDecoder : Decoder Choice
choiceDecoder =
    Decode.map2 Choice
        (Decode.field "value" Decode.string)
        (Decode.field "label" Decode.string)


registrarDecoder : Decoder Registrar
registrarDecoder =
    Decode.map3 Registrar
        (Decode.field "id" Decode.int)
        (Decode.field "username" Decode.string)
        (Decode.field "year" (Decode.nullable Decode.int))


shiftDecoder : Decoder Shift
shiftDecoder =
    Decode.map5 Shift
        (Decode.field "id" Decode.int)
        (Decode.field "date" Decode.string)
        (Decode.field "type" Decode.string)
        (Decode.field "registrar" Decode.int)
        (Decode.field "extra_duty" Decode.bool)


leaveDecoder : Decoder Leave
leaveDecoder =
    Decode.succeed Leave
        |> andMap (Decode.field "id" Decode.int)
        |> andMap (Decode.field "date" Decode.string)
        |> andMap (Decode.field "type" Decode.string)
        |> andMap (Decode.field "portion" Decode.string)
        |> andMap (Decode.field "registrar" Decode.int)
        |> andMap (Decode.field "comment" Decode.string)
        |> andMap (Decode.field "reg_approved" (Decode.nullable Decode.bool))
        |> andMap (Decode.field "dot_approved" (Decode.nullable Decode.bool))
        |> andMap (Decode.field "cancelled" Decode.bool)
        |> andMap (Decode.field "created" Decode.string)
        |> andMap (Decode.field "last_edited" Decode.string)


holidayDecoder : Decoder Holiday
holidayDecoder =
    Decode.map2 Holiday
        (Decode.field "date" Decode.string)
        (Decode.field "name" Decode.string)


publishedDecoder : Decoder Published
publishedDecoder =
    Decode.map2 Published
        (Decode.field "start" Decode.string)
        (Decode.field "end" Decode.string)


rosterDecoder : Decoder Roster
rosterDecoder =
    Decode.succeed Roster
        |> andMap (Decode.field "week" Decode.string)
        |> andMap (Decode.field "prev" Decode.string)
        |> andMap (Decode.field "next" Decode.string)
        |> andMap (Decode.field "today" Decode.string)
        |> andMap (Decode.field "dates" (Decode.list Decode.string))
        |> andMap (Decode.field "registrars" (Decode.list registrarDecoder))
        |> andMap (Decode.field "shifts" (Decode.list shiftDecoder))
        |> andMap (Decode.field "leaves" (Decode.list leaveDecoder))
        |> andMap (Decode.field "holidays" (Decode.list holidayDecoder))
        |> andMap (Decode.field "published" (Decode.nullable publishedDecoder))



-- REQUESTS


getRoster : String -> (Result Http.Error Roster -> msg) -> Cmd msg
getRoster week toMsg =
    Http.get
        { url = "/api/editor/roster?week=" ++ week
        , expect = Http.expectJson toMsg rosterDecoder
        }


{-| Writes send the CSRF token Django checks on unsafe requests.
-}
write : String -> String -> String -> Http.Body -> Http.Expect msg -> Cmd msg
write csrfToken method url body expect =
    Http.request
        { method = method
        , headers = [ Http.header "X-CSRFToken" csrfToken ]
        , url = url
        , body = body
        , expect = expect
        , timeout = Nothing
        , tracker = Nothing
        }


addShift : String -> { date : String, type_ : String, registrar : Int } -> (Result Http.Error Shift -> msg) -> Cmd msg
addShift csrfToken new toMsg =
    write csrfToken
        "POST"
        "/api/editor/shifts"
        (Http.jsonBody
            (Encode.object
                [ ( "date", Encode.string new.date )
                , ( "type", Encode.string new.type_ )
                , ( "registrar", Encode.int new.registrar )
                ]
            )
        )
        (Http.expectJson toMsg shiftDecoder)


changeShift : String -> Int -> List ( String, Encode.Value ) -> (Result Http.Error Shift -> msg) -> Cmd msg
changeShift csrfToken shiftId changes toMsg =
    write csrfToken
        "PATCH"
        ("/api/editor/shifts/" ++ String.fromInt shiftId)
        (Http.jsonBody (Encode.object changes))
        (Http.expectJson toMsg shiftDecoder)


deleteShift : String -> Int -> (Result Http.Error () -> msg) -> Cmd msg
deleteShift csrfToken shiftId toMsg =
    write csrfToken
        "DELETE"
        ("/api/editor/shifts/" ++ String.fromInt shiftId)
        Http.emptyBody
        (Http.expectWhatever toMsg)


changeLeave : String -> Int -> List ( String, Encode.Value ) -> (Result Http.Error Leave -> msg) -> Cmd msg
changeLeave csrfToken leaveId changes toMsg =
    write csrfToken
        "PATCH"
        ("/api/editor/leaves/" ++ String.fromInt leaveId)
        (Http.jsonBody (Encode.object changes))
        (Http.expectJson toMsg leaveDecoder)


httpErrorMessage : Http.Error -> String
httpErrorMessage error =
    case error of
        Http.BadUrl url ->
            "Bad URL: " ++ url

        Http.Timeout ->
            "The server took too long to respond."

        Http.NetworkError ->
            "Couldn't reach the server. Check your connection."

        Http.BadStatus 401 ->
            "You've been signed out. Reload the page to sign in again."

        Http.BadStatus 403 ->
            "The server refused the change. Reload the page and try again."

        Http.BadStatus 404 ->
            "That item no longer exists. Reload the page to see the latest roster."

        Http.BadStatus status ->
            "The server returned an error (" ++ String.fromInt status ++ ")."

        Http.BadBody _ ->
            "The server sent a response the editor didn't understand."
