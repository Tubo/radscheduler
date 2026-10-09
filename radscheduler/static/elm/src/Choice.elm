module Choice exposing (Choice, choiceDecoder, choiceFor)

{-| How the page names its shift, leave and status types. The server sends them, so each department can
name its own.
-}

import Json.Decode as Decode exposing (Decoder)


{-| A shift, leave or status type as the page describes it: stored value, full label, short label for the
grid, and the key that picks it (empty unless it is a shift). Labels live on the server so other
departments can differ.
-}
type alias Choice =
    { value : String
    , label : String
    , short : String
    , key : String
    }


choiceDecoder : Decoder Choice
choiceDecoder =
    Decode.map4 Choice
        (Decode.field "value" Decode.string)
        (Decode.field "label" Decode.string)
        (Decode.field "short" Decode.string)
        (Decode.field "key" Decode.string)


choiceFor : List Choice -> String -> Choice
choiceFor choices value =
    choices
        |> List.filter (\c -> c.value == value)
        |> List.head
        |> Maybe.withDefault { value = value, label = value, short = value, key = "" }
